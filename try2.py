import streamlit as st
import pandas as pd
import re
import io
import zipfile

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
            return None, None, None, f"Unsupported file format: {uploaded_file.name}"

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
            return None, problem_rows, None, f"No 'Unit' column found in {uploaded_file.name}"

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

        # Summary report
        summary = {
            "Original Rows": len(df) + len(problem_rows),
            "Rows with Special Characters": len(problem_rows),
            "Rows After Cleaning": len(df_unique),
            "Duplicate Units Found": len(duplicate_units)
        }

        # Convert cleaned data to CSV
        output_cleaned = io.StringIO()
        df_unique.to_csv(output_cleaned, index=False)

        # Convert problematic rows to CSV
        output_problem = io.StringIO()
        if not problem_rows.empty:
            problem_rows.to_csv(output_problem, index=False)

        return output_cleaned.getvalue(), problem_rows, output_problem.getvalue(), summary

    except Exception as e:
        return None, None, None, f"❌ Error: {e}"

# --- Streamlit UI ---
st.title("🏢 Unit Cleaner Tool (Streamlit)")
uploaded_files = st.file_uploader("Upload Excel or CSV files", type=['xlsx', 'csv'], accept_multiple_files=True)

if uploaded_files:
    delete_special = st.checkbox("Delete rows with special characters (e.g., ñ, #, @)?")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for file in uploaded_files:
            st.subheader(f"File: {file.name}")
            cleaned_csv, problem_rows, problem_csv, summary = process_file(file, delete_special_rows=delete_special)

            if isinstance(summary, dict):
                st.write("### Summary Report")
                st.json(summary)
            else:
                st.error(summary)
                continue

            # Show problematic rows if any
            if problem_rows is not None and not problem_rows.empty:
                st.warning(f"{len(problem_rows)} rows contain special characters:")
                st.dataframe(problem_rows)
                st.download_button(label=f"Download Problematic Rows ({file.name})",
                                   data=problem_csv,
                                   file_name=f"{file.name.split('.')[0]}_problematic.csv",
                                   mime="text/csv")

            # Add cleaned file to ZIP
            if cleaned_csv:
                zip_file.writestr(f"{file.name.split('.')[0]}_cleaned.csv", cleaned_csv)
                st.download_button(label=f"Download Cleaned File ({file.name})",
                                   data=cleaned_csv,
                                   file_name=f"{file.name.split('.')[0]}_cleaned.csv",
                                   mime="text/csv")

    # Multi-file ZIP download
    if zip_buffer.getbuffer().nbytes > 0:
        st.download_button(label="📦 Download All Cleaned Files (ZIP)",
                           data=zip_buffer.getvalue(),
                           file_name="cleaned_files.zip",
                           mime="application/zip")
