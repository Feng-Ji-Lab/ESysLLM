import pandas as pd
import json
import os
import math
import re

# Paths resolved from this file's location (were hard-coded absolute paths).
_here = os.path.dirname(os.path.abspath(__file__))
excel_path = os.path.join(_here, "OSF-T1_edit.xlsx")
papers_folder = os.path.join(_here, "papers_json")
output_path = os.path.join(_here, "ground_truth.json")

columns_to_extract = [
    "SAMPLE SIZE", "ES", "Effects", "Mage", "Measure IQ", 
    "IQ modality", "IQ Aspect", "Creativity Measures", "Domain classified"
]

papers = sorted([d for d in os.listdir(papers_folder) if os.path.isdir(os.path.join(papers_folder, d))])

df = pd.read_excel(excel_path)
actual_cols = df.columns.tolist()

res = {}

for p in papers:
    # extract author and year from folder name
    p_author = p[:-4].lower()
    p_year = p[-4:]
    
    # find row in df
    # Match condition: std_study contains std_p_author and p_year
    def is_match(study_val):
        std_study = re.sub(r'[^a-zA-Z0-9]', '', str(study_val)).lower()
        return p_author in std_study and p_year in std_study

    mask = df["STUDY"].apply(is_match)
    row = df[mask]
    
    print(f"Paper {p}: found {len(row)} rows")
    if len(row) == 0:
        continue
    
    paper_data = {}
    for col in columns_to_extract:
        # find matching column
        match_col = next((c for c in actual_cols if c.lower().strip() == col.lower().strip()), None)
        if not match_col:
            match_col = next((c for c in actual_cols if "".join(c.lower().split()) == "".join(col.lower().split())), None)
            
        if match_col:
            vals = row[match_col].tolist()
            cleaned_vals = []
            for v in vals:
                if pd.isna(v):
                    cleaned_vals.append("none")
                else:
                    if isinstance(v, float) and math.isnan(v):
                        cleaned_vals.append("none")
                    else:
                        cleaned_vals.append(v)
            paper_data[col] = {"study": cleaned_vals}
        else:
            print(f"Column {col} not found for {p}")
            paper_data[col] = {"study": ["none"] * len(row)}
            
    res[p] = paper_data

with open(output_path, 'w') as f:
    json.dump(res, f, indent=4)

print("Created ground_truth.json successfully!")
