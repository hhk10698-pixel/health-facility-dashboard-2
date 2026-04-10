import pandas as pd
import glob
import os

FOLDER_PATH = r"C:\Users\hari\OneDrive\Desktop\Functional PHF"

# Mapping keywords to standard columns
TARGET_COLS = {
    'District': ['dist', 'district', 'dist_name'],
    'Health Block': ['block', 'health block', 'block_name'],
    'Type of Facility (Category)': ['type', 'category', 'facility type', 'facility_type'],
    'Name of Facility': ['facility name', 'name of facility', 'hosp_name', 'facility_name'],
    'Urban/Rural': ['urban', 'rural', 'area']
}

def smart_clean(file_path):
    df = pd.read_excel(file_path)
    # Get the file name (without .xlsx) to use as the State Name
    state_from_filename = os.path.splitext(os.path.basename(file_path))[0]
    
    # Clean column names
    original_cols = {str(c).lower().strip(): c for c in df.columns}
    rename_map = {}
    
    for standard_name, keywords in TARGET_COLS.items():
        for key in keywords:
            match = [orig for clean, orig in original_cols.items() if key in clean]
            if match:
                rename_map[match[0]] = standard_name
                break
    
    df = df.rename(columns=rename_map)
    
    # Standardize Facility Types
    if 'Type of Facility (Category)' in df.columns:
        df['Type of Facility (Category)'] = df['Type of Facility (Category)'].astype(str).str.upper().str.strip()
        # Clean up variations
        df.loc[df['Type of Facility (Category)'].str.contains('SC', na=False), 'Type of Facility (Category)'] = 'SHC'
        df.loc[df['Type of Facility (Category)'].str.contains('SUB', na=False), 'Type of Facility (Category)'] = 'SHC'

    # FORCE the State Name from the filename so the filter works!
    df['Name of State/UTs'] = state_from_filename
    
    # Only keep the columns we need for the dashboard
    final_cols = ['Name of State/UTs'] + [c for c in TARGET_COLS.keys() if c in df.columns]
    return df[final_cols]

if __name__ == "__main__":
    all_files = glob.glob(os.path.join(FOLDER_PATH, "*.xls*"))
    combined_data = []
    
    for f in all_files:
        try:
            print(f"Processing State: {os.path.basename(f)}")
            combined_data.append(smart_clean(f))
        except Exception as e:
            print(f"Error in {f}: {e}")

    if combined_data:
        final_df = pd.concat(combined_data, ignore_index=True)
        final_df.to_csv("master_health_facilities.csv", index=False)
        print("\n✅ Success! Master file created with state-wise tagging.")