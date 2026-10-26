"""PDF Conversion Workflow V2 — Vertex AI variant
======================================================
Forked from format_conversion/run_workflow_v2.py to route Marker's LLM passes
through **Google Vertex AI** (via service-account ADC) instead of the direct
Gemini Developer API.

What changed vs the original:
  * Drops `gemini_api_key` from the Marker config.
  * Adds `llm_service = "marker.services.vertex.GoogleVertexService"`.
  * Adds `vertex_project_id`, `vertex_location`, `gemini_model_name`.
  * Reads `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEX_PROJECT_ID`,
    `VERTEX_LOCATION`, `MAG_GEMINI_MODEL` from `marker_config.env`
    (defaults documented inline).

Run examples:

  # Single PDF (CPU is fine for smoke test):
  python run_workflow_v2_vertex.py \
      --pdf ../PDF/jansen_benchmark/vu2024/Dana2007.pdf \
      --device cpu --use-llm -o ../smoke_vertex_output

  # Whole directory on GPU:
  python run_workflow_v2_vertex.py \
      --pdf-dir ../PDF/jansen_benchmark/vu2024/ \
      --device cuda --use-llm -o ../output_jansen_benchmark/vu2024
"""

import argparse
import base64
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# ENV / CONFIG
# ---------------------------------------------------------------------------

DEFAULT_VERTEX_PROJECT = "gen-lang-client-0512424205"
DEFAULT_VERTEX_LOCATION = "global"
DEFAULT_MODEL = "gemini-2.5-flash"


def load_env_file(env_path: Path) -> None:
    """Parse simple KEY=VALUE lines into os.environ (no shell quoting)."""
    if not env_path.exists():
        return
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


# Prefer the Vertex-specific env file (added for the Jansen benchmark) so we
# don't clobber the original `marker_config.env` (which holds GEMINI_API_KEY
# for the body-appreciation pipeline). Fall back to the default env file so
# anything not duplicated still gets picked up.
load_env_file(Path("marker_config_vertex.env"))
load_env_file(Path("marker_config.env"))


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

def setup_logging(log_file: Optional[Path] = None) -> logging.Logger:
    logger = logging.getLogger("workflow_vertex")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# CORE: convert + crop
# ---------------------------------------------------------------------------

def convert_pdf(pdf_path: Path,
                output_dir: Path,
                use_llm: bool,
                llm_model: Optional[str],
                device: str,
                logger: logging.Logger) -> Optional[Path]:
    """Run Marker (PDF → JSON), writing into `<output_dir>/<stem>/`."""
    os.environ["TORCH_DEVICE"] = device.lower()
    logger.info(f"TORCH_DEVICE={device.lower()}")

    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    stem_dir = output_dir / pdf_path.stem
    stem_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Converting: {pdf_path.name}")
    logger.info(f"Options: device={device}, use_llm={use_llm}, model={llm_model or 'N/A'}")

    config_dict: Dict[str, Any] = {
        "output_format": "json",
        "force_ocr": False,
        "disable_image_extraction": False,
    }

    if use_llm:
        sa_key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not sa_key_path:
            logger.error("GOOGLE_APPLICATION_CREDENTIALS not set "
                         "(put it in marker_config.env)")
            return None
        if not Path(sa_key_path).exists():
            logger.error(f"GOOGLE_APPLICATION_CREDENTIALS file missing: {sa_key_path}")
            return None
        project = os.environ.get("VERTEX_PROJECT_ID", DEFAULT_VERTEX_PROJECT)
        location = os.environ.get("VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
        model = llm_model or os.environ.get("MAG_GEMINI_MODEL", DEFAULT_MODEL)
        logger.info(
            f"Vertex: project={project}, location={location}, model={model}, "
            f"sa_key={sa_key_path}"
        )
        # max_retries / retry_wait_time apply to Marker's BaseGeminiService and
        # absorb the transient 429 / 504 / 499 errors we saw on the global
        # endpoint during the smoke test. us-central1 also has a separate
        # quota pool from the global multiplexer.
        max_retries = int(os.environ.get("MAG_MARKER_MAX_RETRIES", "8"))
        retry_wait = int(os.environ.get("MAG_MARKER_RETRY_WAIT", "10"))
        config_dict.update({
            "use_llm": True,
            "llm_service": "marker.services.vertex.GoogleVertexService",
            "vertex_project_id": project,
            "vertex_location": location,
            "gemini_model_name": model,
            "max_retries": max_retries,
            "retry_wait_time": retry_wait,
        })
        logger.info(f"Marker LLM retry policy: max_retries={max_retries}, "
                    f"retry_wait_time={retry_wait}s")
    else:
        config_dict["use_llm"] = False

    logger.info("Initialising Marker…")
    config_parser = ConfigParser(config_dict)
    artifact_dict = create_model_dict()

    converter_kwargs = {
        "config": config_parser.generate_config_dict(),
        "artifact_dict": artifact_dict,
        "processor_list": config_parser.get_processors(),
        "renderer": config_parser.get_renderer(),
    }
    if use_llm:
        llm_service = config_parser.get_llm_service()
        if llm_service:
            converter_kwargs["llm_service"] = llm_service

    converter = PdfConverter(**converter_kwargs)

    logger.info("Running conversion…")
    rendered = converter(str(pdf_path))

    json_path = stem_dir / f"{pdf_path.stem}.json"
    json_str = rendered.model_dump_json(indent=2)
    json_path.write_text(json_str, encoding="utf-8")
    logger.info(f"Wrote {json_path.name} ({json_path.stat().st_size//1024} KB)")

    # Extract embedded images (Marker stores base64 alongside blocks)
    images_dir = stem_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_count = 0

    json_data = json.loads(json_str)

    def walk_images(block: Dict, page_idx: int) -> None:
        nonlocal image_count
        for img_id, img_b64 in (block.get("images") or {}).items():
            if img_b64 is None:
                continue
            ext = "jpg" if img_b64.startswith("/9j/") else "png"
            safe = img_id.replace("/", "_")
            try:
                (images_dir / f"p{page_idx:03d}_{safe}.{ext}").write_bytes(
                    base64.b64decode(img_b64)
                )
                image_count += 1
            except Exception:
                pass
        for child in (block.get("children") or []):
            walk_images(child, page_idx)

    for idx, child in enumerate(json_data.get("children") or []):
        walk_images(child, idx)
    if image_count:
        logger.info(f"Extracted {image_count} embedded images")

    # Meta
    (stem_dir / f"{pdf_path.stem}_meta.json").write_text(json.dumps({
        "conversion_time": datetime.now().isoformat(),
        "llm_used": use_llm,
        "llm_service": "vertex" if use_llm else None,
        "llm_model": llm_model or os.environ.get("MAG_GEMINI_MODEL", DEFAULT_MODEL),
        "device": device,
    }, indent=2), encoding="utf-8")

    return json_path


def extract_tables(pdf_path: Path,
                   json_path: Path,
                   output_dir: Path,
                   logger: logging.Logger) -> int:
    from table_cropper import CropConfig, process_pdf, save_manifest
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    pages = json_data.get("children", []) if isinstance(json_data, dict) else json_data
    table_dir = output_dir / pdf_path.stem / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    crops = process_pdf(
        pdf_path=pdf_path,
        json_data=pages,
        output_dir=table_dir,
        config=CropConfig(margin=10.0, dpi=300, image_format="png"),
        logger=logger,
    )
    if crops:
        save_manifest(crops, table_dir / "manifest.json")
        logger.info(f"Saved {len(crops)} table crops to {table_dir}")
    return len(crops)


def extract_figures(pdf_path: Path,
                    json_path: Path,
                    output_dir: Path,
                    logger: logging.Logger) -> int:
    from figure_cropper import FigureCropConfig, process_pdf as proc_figs, save_manifest
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    pages = json_data.get("children", []) if isinstance(json_data, dict) else json_data
    fig_dir = output_dir / pdf_path.stem / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    crops = proc_figs(
        pdf_path=pdf_path,
        json_data=pages,
        output_dir=fig_dir,
        config=FigureCropConfig(margin=10.0, dpi=300, image_format="png"),
        logger=logger,
    )
    if crops:
        save_manifest(crops, fig_dir / "manifest.json")
        logger.info(f"Saved {len(crops)} figure crops to {fig_dir}")
    return len(crops)


def process_file(pdf_path: Path,
                 output_dir: Path,
                 use_llm: bool,
                 llm_model: Optional[str],
                 device: str,
                 logger: logging.Logger) -> bool:
    start = datetime.now()
    logger.info("=" * 60)
    logger.info(f"PROCESSING: {pdf_path.name}")
    logger.info("=" * 60)

    json_path = convert_pdf(pdf_path, output_dir, use_llm, llm_model, device, logger)
    if not json_path:
        logger.error("Conversion step failed.")
        return False

    try:
        extract_tables(pdf_path, json_path, output_dir, logger)
    except Exception as exc:
        logger.warning(f"Table extraction failed: {exc}")
    try:
        extract_figures(pdf_path, json_path, output_dir, logger)
    except Exception as exc:
        logger.warning(f"Figure extraction failed: {exc}")

    logger.info(f"Completed in {(datetime.now()-start).total_seconds():.1f}s")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="PDF Marker Workflow — Vertex AI variant")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--pdf", type=Path, help="single PDF")
    g.add_argument("--pdf-dir", type=Path, help="directory of PDFs")
    p.add_argument("-o", "--output", type=Path, default=Path("output_vertex"),
                   help="output directory (default: output_vertex)")
    p.add_argument("--use-llm", action="store_true", help="enable Vertex Gemini")
    p.add_argument("--llm-model", type=str, default=None,
                   help=f"override Gemini model name (default: ${{MAG_GEMINI_MODEL}} "
                        f"or {DEFAULT_MODEL})")
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    args = p.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    logger = setup_logging()

    if args.device == "cuda":
        try:
            import torch
            if not torch.cuda.is_available():
                logger.warning("CUDA requested but not available — Marker will fall back.")
        except ImportError:
            pass

    if args.pdf:
        if not args.pdf.exists():
            logger.error(f"File not found: {args.pdf}")
            sys.exit(1)
        ok = process_file(args.pdf, args.output, args.use_llm, args.llm_model,
                          args.device, logger)
        sys.exit(0 if ok else 1)

    files = sorted(args.pdf_dir.glob("*.pdf"))
    logger.info(f"Found {len(files)} PDFs in {args.pdf_dir}")
    ok_count = 0
    for f in files:
        if process_file(f, args.output, args.use_llm, args.llm_model,
                        args.device, logger):
            ok_count += 1
    logger.info(f"Batch complete: {ok_count}/{len(files)} successful")
    sys.exit(0 if ok_count == len(files) else 1)


if __name__ == "__main__":
    main()
