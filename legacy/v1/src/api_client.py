import json
import time
import os
import copy
from typing import Dict, Any, List

def _lowercase_schema_types(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively lowercase 'type' values in a JSON schema to ensure standard JSON Schema format."""
    if not isinstance(schema, dict):
        return schema
    
    new_schema = copy.deepcopy(schema)
    if "type" in new_schema and isinstance(new_schema["type"], str):
        new_schema["type"] = new_schema["type"].lower()
    
    if "properties" in new_schema:
        for k, v in new_schema["properties"].items():
            new_schema["properties"][k] = _lowercase_schema_types(v)
            
    if "items" in new_schema:
        new_schema["items"] = _lowercase_schema_types(new_schema["items"])
        
    if "anyOf" in new_schema:
        new_schema["anyOf"] = [_lowercase_schema_types(opt) for opt in new_schema["anyOf"]]
        
    return new_schema

def _sanitize_schema_keys(schema: Dict[str, Any], key_mapping: Dict[str, str]) -> Dict[str, Any]:
    """Recursively sanitize property keys to match Anthropic requirements and populate key_mapping."""
    if not isinstance(schema, dict):
        return schema
        
    new_schema = copy.deepcopy(schema)
    import re
    
    if "properties" in new_schema and isinstance(new_schema["properties"], dict):
        new_props = {}
        for k, v in new_schema["properties"].items():
            sanitized_k = re.sub(r'[^a-zA-Z0-9_.-]', '_', k)[:64]
            if sanitized_k != k:
                key_mapping[sanitized_k] = k
            new_props[sanitized_k] = _sanitize_schema_keys(v, key_mapping)
        new_schema["properties"] = new_props
        
    if "items" in new_schema:
        new_schema["items"] = _sanitize_schema_keys(new_schema["items"], key_mapping)
        
    if "anyOf" in new_schema:
        new_schema["anyOf"] = [_sanitize_schema_keys(opt, key_mapping) for opt in new_schema["anyOf"]]
        
    # Also fix required fields
    if "required" in new_schema and isinstance(new_schema["required"], list):
        new_reqs = []
        for req in new_schema["required"]:
            sanitized_req = re.sub(r'[^a-zA-Z0-9_.-]', '_', req)[:64]
            new_reqs.append(sanitized_req)
        new_schema["required"] = new_reqs
        
    return new_schema

def _restore_schema_keys(data: Any, key_mapping: Dict[str, str]) -> Any:
    """Recursively restore original keys in the data returned by Anthropic."""
    if isinstance(data, dict):
        restored_data = {}
        for k, v in data.items():
            original_k = key_mapping.get(k, k)
            restored_data[original_k] = _restore_schema_keys(v, key_mapping)
        return restored_data
    elif isinstance(data, list):
        return [_restore_schema_keys(item, key_mapping) for item in data]
    else:
        return data


def _restore_dynamic_dicts(data: Any) -> Any:
    """Recursively transforms arrays of {"key": ..., "value": ...} back to a dictionary."""
    if isinstance(data, dict):
        return {k: _restore_dynamic_dicts(v) for k, v in data.items()}
    elif isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], dict) and "key" in data[0] and "value" in data[0]:
            restored_dict = {}
            for item in data:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    restored_dict[item["key"]] = _restore_dynamic_dicts(item["value"])
            return restored_dict
        else:
            return [_restore_dynamic_dicts(item) for item in data]
    return data


def _prepare_openai_schema(schema: Dict[str, Any], name: str = "json_schema") -> Dict[str, Any]:
    """Wraps JSON schema into OpenAI Structured Outputs 'json_schema' format."""
    clean_schema = _lowercase_schema_types(schema)
    # OpenAI requires 'additionalProperties': False in objects by default in strict mode
    # For now, we just pass the schema, strict=True usually requires it.
    # We will just pass it standard json_schema without strict=True unless needed.
    return {
        "name": name,
        "schema": clean_schema,
        "strict": False
    }

def _prepare_gemini_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively clean up schema for Gemini by removing unsupported keys like additionalProperties."""
    if not isinstance(schema, dict):
        return schema
        
    new_schema = copy.deepcopy(schema)
    
    # Gemini does not support additionalProperties
    if "additionalProperties" in new_schema:
        del new_schema["additionalProperties"]
        
    if "properties" in new_schema:
        for k, v in new_schema["properties"].items():
            new_schema["properties"][k] = _prepare_gemini_schema(v)
            
    if "items" in new_schema:
        new_schema["items"] = _prepare_gemini_schema(new_schema["items"])
        
    if "anyOf" in new_schema:
        new_schema["anyOf"] = [_prepare_gemini_schema(opt) for opt in new_schema["anyOf"]]
        
    return new_schema

class APIClient:
    def __init__(self, config):
        self.config = config
        self.api_key = config.api_key
        self.model_name = config.model_name
        self.temperature = config.settings.get("temperature", 0.0) if hasattr(config, "settings") and isinstance(config.settings, dict) else 0.0
        
        self.is_openai = self.model_name.startswith("gpt-") or self.model_name.startswith("o1") or self.model_name.startswith("o3")
        self.is_gemini = self.model_name.startswith("gemini-")
        self.is_anthropic = self.model_name.startswith("claude-")
        
        if self.is_openai:
            import openai
            self.openai_client = openai.OpenAI(api_key=self.api_key)
        elif self.is_gemini:
            from google import genai
            self.gemini_client = genai.Client(api_key=self.api_key)
        elif self.is_anthropic:
            import anthropic
            self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)
        else:
            print(f"Warning: Unknown model prefix for {self.model_name}. Attempting to use OpenAI compatible client.")
            import openai
            self.is_openai = True
            # For some local endpoints you might need custom base_url, we just use default openai setup here.
            self.openai_client = openai.OpenAI(api_key=self.api_key)

    def generate_content(
        self,
        system_instruction: str,
        user_content: str,
        response_schema: Dict[str, Any],
        assets: List[Dict[str, Any]] = None,
        retry_count: int = 2
    ) -> Dict[str, Any]:
        """
        Calls the appropriate model API.
        
        assets: list of dicts with 'path', 'mime_type', 'data' (bytes).
                For Gemini, we use types.Blob.
                For OpenAI, we can use base64 encoded strings in the messages format.
        """
        for attempt in range(retry_count + 1):
            try:
                if self.is_gemini:
                    res = self._call_gemini(system_instruction, user_content, response_schema, self.temperature, assets)
                elif self.is_anthropic:
                    res = self._call_anthropic(system_instruction, user_content, response_schema, self.temperature, assets)
                else:
                    res = self._call_openai(system_instruction, user_content, response_schema, self.temperature, assets)
                
                if isinstance(res, dict) and "error" not in res:
                    res = _restore_dynamic_dicts(res)
                return res
            except Exception as e:
                if attempt < retry_count:
                    print(f"API calling error: {e}. Retrying in 5 seconds ({attempt + 1}/{retry_count})...")
                    time.sleep(5)
                else:
                    return {"error": str(e)}

    def _call_gemini(self, system_instruction: str, user_content: str, response_schema: Dict[str, Any], temperature: float, assets: List[Dict[str, Any]]) -> Dict[str, Any]:
        from google.genai import types
        request_parts = [types.Part(text=user_content)]
        if assets:
            for asset in assets:
                request_parts.append(types.Part(
                    inline_data=types.Blob(
                        mime_type=asset["mime_type"],
                        data=asset["data"]
                    )
                ))
                
        clean_schema = _lowercase_schema_types(response_schema)
        gemini_schema = _prepare_gemini_schema(clean_schema)
        
        response = self.gemini_client.models.generate_content(
            model=self.model_name,
            contents=[types.Content(role="user", parts=request_parts)],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=gemini_schema,
                temperature=temperature
            )
        )
        
        if response.text:
            return json.loads(response.text)
        return {"error": "Empty response from Gemini model"}

    def _call_openai(self, system_instruction: str, user_content: str, response_schema: Dict[str, Any], temperature: float, assets: List[Dict[str, Any]]) -> Dict[str, Any]:
        import base64
        
        # Build messages
        messages = [
            {"role": "system", "content": system_instruction}
        ]
        
        user_message = {"role": "user", "content": [{"type": "text", "text": user_content}]}
        
        if assets:
            for asset in assets:
                encoded = base64.b64encode(asset["data"]).decode('utf-8')
                user_message["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{asset['mime_type']};base64,{encoded}"
                    }
                })
                
        messages.append(user_message)
        
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": _prepare_openai_schema(response_schema)
            }
        }
        
        if not (self.model_name.startswith("o1") or self.model_name.startswith("o3") or self.model_name.startswith("gpt-5")):
            kwargs["temperature"] = temperature
        elif temperature == 1:
            kwargs["temperature"] = 1
            
        try:
            response = self.openai_client.chat.completions.create(**kwargs)
        except Exception as e:
            if "temperature" in str(e).lower() and "temperature" in kwargs:
                # Retry without temperature if the model does not support it
                del kwargs["temperature"]
                response = self.openai_client.chat.completions.create(**kwargs)
            else:
                raise e
        
        content = response.choices[0].message.content
        if content:
            return json.loads(content)
        return {"error": "Empty response from OpenAI model"}

    def _call_anthropic(self, system_instruction: str, user_content: str, response_schema: Dict[str, Any], temperature: float, assets: List[Dict[str, Any]]) -> Dict[str, Any]:
        import base64
        
        user_message_content = []
        
        if assets:
            for asset in assets:
                encoded = base64.b64encode(asset["data"]).decode('utf-8')
                media_type = asset["mime_type"]
                user_message_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": encoded
                    }
                })
                
        user_message_content.append({"type": "text", "text": user_content})
        
        clean_schema = _lowercase_schema_types(response_schema)
        
        # Sanitize keys for Anthropic
        key_mapping = {}
        sanitized_schema = _sanitize_schema_keys(clean_schema, key_mapping)
        
        tool_name = "extract_data"
        
        tools = [
            {
                "name": tool_name,
                "description": "Extract structured data according to the schema",
                "input_schema": sanitized_schema
            }
        ]
        
        try:
            response = self.anthropic_client.messages.create(
                model=self.model_name,
                system=system_instruction,
                messages=[{"role": "user", "content": user_message_content}],
                tools=tools,
                tool_choice={"type": "tool", "name": tool_name},
                temperature=temperature,
                max_tokens=4096
            )
        except Exception as e:
            raise e
            
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return _restore_schema_keys(block.input, key_mapping)
                
        return {"error": "Empty or unrecognized response from Anthropic model"}
