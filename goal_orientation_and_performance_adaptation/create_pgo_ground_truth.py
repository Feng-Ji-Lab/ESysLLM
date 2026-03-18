import pandas as pd
import json
import os

def create_ground_truth():
    # File paths
    base_dir = r"/home/ubuntu/nanyu/llm_meta_analysis_new"
    csv_path = os.path.join(base_dir, "goal_orientation_and_performance_adaptation", "PGO_PA_2019.csv")
    output_path = os.path.join(base_dir, "goal_orientation_and_performance_adaptation", "ground_truth.json")

    # Load CSV
    df = pd.read_csv(csv_path)

    # Clean Author and PubYear to ensure they are strings and handle any missing values if necessary
    df['Author'] = df['Author'].astype(str).str.strip()
    df['PubYear'] = df['PubYear'].astype(str).str.strip()

    # Create Paper Key
    df['PaperKey'] = df['Author'] + df['PubYear']

    # Remap AdaptMethod
    # 1 -> 0, 2 -> 1
    # Check for values other than 1 and 2 just in case, though requirement is specific
    # Using map or replace.
    df['AdaptMethod'] = df['AdaptMethod'].map({1: 0, 2: 1})
    # Fill NaN if any map failed (though strictly speaking we expect 1 or 2) - keeping as is or ensure type
    # If there are NaNs in original, they remain NaN.

    # Required columns and mapping
    column_mapping = {
        "PgoType": "PgoType",
        "AdaptMeasures": "AdaptMeasures",
        "AdaptMethod": "AdaptMethod",
        "AdaptMethod_Specific": "AdaptMethod_Specific",
        "GoMeasure_dichot_num": "GoMeasure_dichot_num",
        "AgeInfo": "Age_Info",
        "Age_imputed": "Age_imputed",
        "Sex": "Sex",
        "Men_Prop": "Men_Prop",
        "Country_dichot_num": "Country_dichot_num",
        "Sample_dichot": "Sample_dichot",
        "N": "N",
        "yi": "Correlation_PGO_and_PA",
        "Effect_Info": "Correlation_info"
    }
    
    # Columns that are paper-level (should have only one value per paper)
    paper_level_columns = {
        "PubType": "PubType",
        "FinancSupport": "FinancSupport",
        "PeerReview": "PeerReview"
    }

    # Iterate through each paper
    ground_truth = {}

    for paper_key, paper_group in df.groupby('PaperKey'):
        paper_dict = {}
        
        # Determine strict order of attributes to match "ground_truth.json" structure roughly?
        # The user said: "Then for each field, it should be a dictionary like @[ground_truth.json]. 
        # And the number of keys are as the same as the number of distinct IDs in the "ID" column...
        # You should name the key as "Study 1", "Study 2" and etc. 
        # Then for all rows with the same ID, you should put them in the list with the corresponding key in the dictionary."

        # Get unique IDs for this paper and sort them to assign "Study 1", "Study 2", etc.
        unique_ids = sorted(paper_group['ID'].unique())
        
        # Map ID to "Study X"
        id_to_study_name = {uid: f"Study {i+1}" for i, uid in enumerate(unique_ids)}

        # Initialize the dictionaries for each required field
        # We need to iterate over the columns we want to export
        
        # Initialize dictionary for each target column with "Study X": []
        fields_data = {target_col: {s_name: [] for s_name in id_to_study_name.values()} 
                       for target_col in column_mapping.values()}

        # Go through rows
        for _, row in paper_group.iterrows():
            study_name = id_to_study_name[row['ID']]
            
            for src_col, target_col in column_mapping.items():
                val = row[src_col]
                # Handle NaN - JSON doesn't support NaN. Convert to None or keep as is if json.dump handles it (it dumps as null)
                # Ideally, we want native python types.
                if pd.isna(val):
                    val = None
                
                fields_data[target_col][study_name].append(val)

        # Assign to paper dict
        for target_col, study_dict in fields_data.items():
            # Check if lists in study_dict contain identical values and reduce them
            for s_name, data_list in study_dict.items():
                if len(data_list) > 1:
                    # Check if all elements are the same
                    # Use a set to check uniqueness, but lists are not hashable if they contain lists (unlikely here)
                    # elements are likely primitives (str, int, float, None)
                    
                    # Handle NaNs which might be distinct objects in some contexts, but here we likely have None or primitives
                    first_elem = data_list[0]
                    all_same = True
                    for elem in data_list[1:]:
                        if elem != first_elem:
                            all_same = False
                            break
                    
                    if all_same:
                        study_dict[s_name] = [first_elem]

            paper_dict[target_col] = study_dict

        # Process paper-level columns
        # We assume these values are identical for all rows in the paper. We take the first one.
        for src_col, target_col in paper_level_columns.items():
            # Get the first value from the group
            val = paper_group[src_col].iloc[0]
            if pd.isna(val):
                val = None
            
            # User requirement: put it in the list of a dictionary with one key "Study" like {"Study":[]}
            # Based on user request: "just need to put it in the list of a dictionary with one key "Study" like {"Study":[]}"
            
            # Convert to native python type if it's a numpy type
            if hasattr(val, 'item'):
                val = val.item()
                
            paper_dict[target_col] = {"Study": [val]}
            
        ground_truth[paper_key] = paper_dict

    # Determine matching PDF file names?
    # User said: "Then for each paper, the corresponding pdf file name in the .../papers_pdf is the "Author"+"PubYear""
    # The JSON structure key is Author+PubYear, so that's already handled.
    
    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=4)

    print(f"Ground truth generated at: {output_path}")

if __name__ == "__main__":
    create_ground_truth()
