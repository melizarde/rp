import pandas as pd
import os
import re 
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
 

def contains_special_chars(s):
    if pd.isna(s):
        return False

    pattern = re.compile(r'[^a-zA-Z0-9\s-]')
    return bool(pattern.search(str(s)))
 

class SpecialCharDialog(tk.Toplevel):
    def __init__(self, parent, problem_df):
        super().__init__(parent)
        self.title("Special Character Review")
        self.geometry("750x500")
        self.result = "cancel"  
 
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill='both', expand=True)
 
        label = ttk.Label(main_frame, text="The following rows contain special characters (e.g., ñ, #, @).\nChoose whether to keep or delete them before proceeding.", justify='center')
        label.pack(pady=(0, 10))
 
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True)
       
        tree_scroll_y = ttk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')
 
        self.tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        self.tree.pack(fill='both', expand=True)
       
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
 
        # --- Populate Treeview ---
        self.tree["columns"] = list(problem_df.columns)
        self.tree["show"] = "headings"
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
       
        for index, row in problem_df.iterrows():
            self.tree.insert("", "end", values=list(row))
 

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
 
        keep_button = ttk.Button(button_frame, text="Keep These Rows", command=self.on_keep)
        keep_button.pack(side='left', expand=True, padx=5)
       
        delete_button = ttk.Button(button_frame, text="Delete These Rows", command=self.on_delete)
        delete_button.pack(side='left', expand=True, padx=5)
 

        self.transient(parent)
        self.grab_set()
 
    def on_keep(self):
        self.result = "keep"
        self.destroy()
 
    def on_delete(self):
        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to permanently delete these rows?"):
            self.result = "delete"
            self.destroy()
 
def read_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.xlsx':
        return pd.read_excel(file_path, dtype=str, keep_default_na=False, engine='openpyxl')
    elif ext == '.csv':
        return pd.read_csv(file_path, dtype=str, keep_default_na=False)
    else:
        raise ValueError(f"Unsupported file format for {file_path}. Please use .csv or .xlsx")
 
def clean_tower(tower_value):
    if not tower_value or str(tower_value).strip().lower() in ['n/a', 'na', '', 'N/A']:
        return ''
    return str(tower_value).strip()
 

def clean_units(file_path, parent_window):
    try:
        df = read_file(file_path)
 
        special_char_mask = df.apply(lambda row: row.astype(str).apply(contains_special_chars).any(), axis=1)
        problem_rows = df[special_char_mask]
       
        deleted_rows_count = 0
       

        if not problem_rows.empty:
            dialog = SpecialCharDialog(parent_window, problem_rows)
            parent_window.wait_window(dialog)
           
            choice = dialog.result
           
            if choice == "delete":
            
                df.drop(problem_rows.index, inplace=True)
                deleted_rows_count = len(problem_rows)
            elif choice == "cancel":
                
                return f"🟡 Canceled processing for {os.path.basename(file_path)}."
 
       
        tower_col = next((c for c in df.columns if 'tower' in c.lower()), None)
        unit_col = next((c for c in df.columns if 'unit' in c.lower()), None)
        corp_col = next((c for c in df.columns if 'corporate' in c.lower()), None)
 
        if not unit_col:
            return f"⚠️ No 'Unit' column found in {file_path}."
 
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
        df_unique = df_unique.drop_duplicates()
        df_unique.drop(columns=['_CleanUnit'], inplace=True)
        df_unique.replace({'N/A': '', 'n/a': '', 'na': '', '': ''}, inplace=True)
 
        output_file = os.path.splitext(file_path)[0] + "_cleaned.csv"
        df_unique.to_csv(output_file, index=False, quoting=1)
 
        ## NEW: Add information about deleted rows to the result message
        result_message = f"✅ Processed: {os.path.basename(file_path)}\n"
        if deleted_rows_count > 0:
            result_message += f"🗑️ Deleted {deleted_rows_count} rows with special characters.\n"
        result_message += f"📁 Saved as: {output_file}\n🔢 Total Unique Units: {len(df_unique)}"
       
        return result_message
 
    except Exception as e:
        return f"❌ Error processing {file_path}: {e}"
 
## MODIFIED: The process_files function now passes the 'root' window to clean_units.
def process_files():
    file_paths = filedialog.askopenfilenames(
        title="Select Excel or CSV Files",
        filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
    )
    if not file_paths:
        messagebox.showinfo("No Selection", "No files selected.")
        return
 
    progress_bar.start()
    root.update_idletasks()
   
    # Pass the root window to the processing function
    results = [clean_units(file_path, root) for file_path in file_paths]
 
    progress_bar.stop()
 
    result_box.config(state='normal')
    result_box.delete(1.0, tk.END)
    result_box.insert(tk.END, "\n\n".join(results))
    result_box.config(state='disabled')
 
def clear_results():
    result_box.config(state='normal')
    result_box.delete(1.0, tk.END)
    result_box.config(state='disabled')
 
# --- GUI Setup (Unchanged) ---
root = tk.Tk()
root.title("🏢 Unit Cleaner Tool")
root.geometry("800x600")
root.resizable(True, True)
 
style = ttk.Style()
style.theme_use('clam')
 
frame = ttk.Frame(root, padding="20")
frame.pack(fill='both', expand=True)
 
label = ttk.Label(frame, text="📂 Select files to clean unit data:", font=("Segoe UI", 12))
label.pack(pady=10)
 
button_frame = ttk.Frame(frame)
button_frame.pack(pady=5)
 
select_button = ttk.Button(button_frame, text="Select Files", command=process_files)
select_button.pack(side='left', padx=5)
 
clear_button = ttk.Button(button_frame, text="Clear Results", command=clear_results)
clear_button.pack(side='left', padx=5)
 
progress_bar = ttk.Progressbar(frame, mode='indeterminate')
progress_bar.pack(fill='x', pady=10)
 
result_frame = ttk.Frame(frame)
result_frame.pack(fill='both', expand=True)
 
scrollbar = ttk.Scrollbar(result_frame)
scrollbar.pack(side='right', fill='y')
 
result_box = tk.Text(result_frame, wrap='word', height=20, state='disabled', yscrollcommand=scrollbar.set)
result_box.pack(fill='both', expand=True)
scrollbar.config(command=result_box.yview)
 
root.mainloop()