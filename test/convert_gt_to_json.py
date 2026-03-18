import pandas as pd
import json
import os

GT_PATH = "true_value_sy.xlsx"
OUTPUT_PATH = "ground_truth.json"

def main():
    if not os.path.exists(GT_PATH):
        print(f"Error: {GT_PATH} not found.")
        return

    print(f"Reading {GT_PATH}...")
    try:
        df = pd.read_excel(GT_PATH)
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    # Check if 'filename' column exists
    if 'filename' not in df.columns:
        print("Error: 'filename' column not found in Excel. Cannot use as key.")
        # Fallback to list of records?
        # print("Saving as list of records...")
        # data = df.to_dict(orient='records')
        return

    # Convert to dictionary keyed by filename
    # Drop rows where filename is NaN
    df = df.dropna(subset=['filename'])
    
    # Clean filename (strip whitespace, ensure string)
    df['filename'] = df['filename'].astype(str).str.strip()
    
    # set index and transpose
    data = df.set_index('filename').to_dict(orient='index')
    
    # Gender Consolidation Logic
    gender_map = {
        "Sample": {"male": "Male Sample Size", "female": "Female Sample Size"},
        "Mean age of participants": {"male": "Mean age of male participants", "female": "Mean age of female participants"},
        "Mean BMI of participants": {"male": "Mean BMI of male participants", "female": "Mean BMI of female participants"},
        "Percent of white in participants": {"male": "Percent of white male participants", "female": "Percent of white female participants"},
        "Percentage of college or higher of participants": {"male": "Percent of college or higher male participants", "female": "Percent of college or higher female participants"},
        "Correlation between body appreciation and BMI": {"male": "Correlation between male body appreciation and BMI", "female": "Correlation between female body appreciation and BMI"}
    }

    clean_data = {}
    for fname, props in data.items():
        clean_props = {}
        # 1. Copy non-gender properties first
        # Identify columns to skip (involved in gender map)
        skip_cols = set()
        for info in gender_map.values():
            skip_cols.add(info["male"])
            skip_cols.add(info["female"])
            
        for k, v in props.items():
            if k in skip_cols: continue
            if pd.isna(v) or str(v).lower() == 'none':
                clean_props[k] = []
            else:
                clean_props[k] = [v]
                
        # 2. Process Gender Fields
        for target_key, cols in gender_map.items():
            m_col = cols["male"]
            f_col = cols["female"]
            
            val_m = props.get(m_col)
            val_f = props.get(f_col)
            
            # Normalize to None if NaN
            if pd.isna(val_m): val_m = None
            if pd.isna(val_f): val_f = None
            
            # Logic: 
            # If M == F (and not None) -> total: [val], m: [], f: []
            # Else -> total: [], m: [val], f: [val]
            
            sub_dict = {"male": [], "female": [], "total": []}
            
            # Check equality (handle float precision?)
            is_same = False
            if val_m is not None and val_f is not None:
                if val_m == val_f:
                    is_same = True
                    
            if is_same:
                sub_dict["total"] = [val_m]
            else:
                if val_m is not None:
                    sub_dict["male"] = [val_m]
                if val_f is not None:
                    sub_dict["female"] = [val_f]
            
            clean_props[target_key] = sub_dict
            
        clean_data[fname] = clean_props

    print(f"converted {len(clean_data)} records.")
    
    print(f"Saving to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, indent=2)
        
    print("Done.")

if __name__ == "__main__":
    main()
