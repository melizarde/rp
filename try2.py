import streamlit as st
import pandas as pd
import re
import io

# --- Helper Functions ---
def contains_special_chars(s):
    if pd.isna(s):
        return False
    pattern = re.compile(r'[^a-zA-Z0-9\s\-]')
    return bool(pattern.search(str(s)))

def clean_tower(tower_value):
    if not tower_value or str(tower_value).strip().lower() in ['n/a', 'na', '', 'N/A']:
        return ''
    return str(tower_value).strip()

def process_file(uploaded_file, delete_special_rows=False):
    try:
        ext = uploaded_file.name.split('.')[-1].lower()
        if ext == 'xlsx':
            df = pd.read_excel(uploaded_file, dtype=str, keep_default_na=False, engine='openpyxl')
        elif ext == 'csv':
            df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
        else:
            return None, f"Unsupported file format: {uploaded_file.name}"

        # Detect special characters
        special_char_mask = df.apply(lambda row: row.astype(str).apply(contains_special_chars).any(), axis=1)
        problem_rows = df[special_char_mask]

        if delete_special_rows and not problem_rows.empty:
            df.drop(problem_rows.index, inplace=True)

        # Identify columns
        tower_col = next((c for c in df.columns if 'tower' in c.lower()), None)
        unit_col = next((c for c in df.columns if 'unit' in c.lower()), None)
        corp_col = next((c for c in df.columns if 'corporate' in c.lower()), None)

        if not unit_col:
            return None, f"No 'Unit' column found in {uploaded_file.name}"

        df['_CleanUnit'] = df[unit_col].apply(lambda x: x.strip())
        duplicate_units = df[df.duplicated('_CleanUnit', keep=False)]

        def build_unit(row):
            unit = row['_CleanUnit']
            tower = clean_tower(row[tower_col]) if tower_col else ''
            corp = row[corp_col].strip() if corp_col and pd.notna(row[corp_col]) else ''
            if unit in duplicate_units['_CleanUnit'].values:
                same_unit_rows = duplicate_units[duplicate_units['_CleanUnit'] == unit]
                unique_towers = same_unit_rows[tower_col].dropna().apply(clean_tower).unique()
                if tower and len(unique_towers) > 1:
                    return f"{tower} - {unit}"
                elif tower and corp:
                    return f"{tower} - {unit} - {corp}"
                elif tower:
                    return f"{tower} - {unit}"
                else:
                    return unit
            else:
                return unit

        df['Unit'] = df.apply(build_unit, axis=1)
        df_unique = df.drop_duplicates(subset=['Unit']).reset_index(drop=True)
        df_unique.drop(columns=['_CleanUnit'], inplace=True)
        df_unique.replace({'N/A': '', 'n/a': '', 'na': '', '': ''}, inplace=True)

        # Convert to CSV for download
        output = io.StringIO()
        df_unique.to_csv(output, index=False)
        return output.getvalue(), f"✅ Processed {uploaded_file.name} | Unique Units: {len(df_unique)}"

    except Exception as e:
        return None, f"❌ Error: {e}"

# --- Streamlit UI ---
st.title("🏢 Unit Cleaner Tool (Streamlit)")
uploaded_files = st.file_uploader("Upload Excel or CSV files", type=['xlsx', 'csv'], accept_multiple_files=True)

if uploaded_files:
    delete_special = st.checkbox("Delete rows with special characters (e.g., ñ, #, @)?")
    for file in uploaded_files:
        st.subheader(f"File: {file.name}")
        csv_data, message = process_file(file, delete_special_rows=delete_special)
        st.write(message)
        if csv_data:
            st.download_button(label="Download Cleaned File", data=csv_data, file_name=f"{file.name.split('.')[0]}_cleaned.csv", mime="text/csv")
