import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import os
import json
import zipfile
import threading
import shutil
import sys
import ctypes
import subprocess
from datetime import datetime

CONFIG_FILE = "config.json"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class ConfigManager:
    def __init__(self):
        self.config = {
            "current_profile": "Default",
            "profiles": {
                "Default": []
            }
        }
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_profiles(self):
        return list(self.config["profiles"].keys())

    def get_current_profile(self):
        return self.config["current_profile"]

    def set_current_profile(self, name):
        if name in self.config["profiles"]:
            self.config["current_profile"] = name
            self.save()

    def add_profile(self, name):
        if name not in self.config["profiles"]:
            self.config["profiles"][name] = []
            self.save()

    def delete_profile(self, name):
        if name in self.config["profiles"] and len(self.config["profiles"]) > 1:
            del self.config["profiles"][name]
            # Reset current if deleted
            if self.config["current_profile"] == name:
                self.config["current_profile"] = list(self.config["profiles"].keys())[0]
            self.save()

    def get_paths(self):
        prof = self.config["current_profile"]
        return self.config["profiles"].get(prof, [])

    def add_path(self, path):
        prof = self.config["current_profile"]
        if path not in self.config["profiles"][prof]:
            self.config["profiles"][prof].append(path)
            self.save()

    def remove_path(self, path):
        prof = self.config["current_profile"]
        if path in self.config["profiles"][prof]:
            self.config["profiles"][prof].remove(path)
            self.save()

class PreviewDialog(tk.Toplevel):
    def __init__(self, parent, zip_path, restore_map, on_confirm):
        super().__init__(parent)
        self.title("Restore Preview - Confirm Actions")
        self.geometry("600x400")
        self.transient(parent)
        # self.grab_set() # Optional: Modal
        
        self.zip_path = zip_path
        self.restore_map = restore_map
        self.on_confirm = on_confirm
        
        # --- UI ---
        lbl_info = tk.Label(self, text="The following locations will be RESTORED (overwritten if exist):", font=("Arial", 10, "bold"), pady=10)
        lbl_info.pack(fill=tk.X, padx=10)
        
        # Treeview to show paths
        columns = ("path", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("path", text="Target Path")
        self.tree.heading("status", text="Current Status")
        self.tree.column("path", width=400)
        self.tree.column("status", width=150)
        
        # Add Scrollbar
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10)
        
        # Populate
        self._populate_list()
        
        # Buttons
        btn_frame = tk.Frame(self, pady=10)
        btn_frame.pack(fill=tk.X)
        
        btn_cancel = tk.Button(btn_frame, text="Cancel", command=self.destroy, width=15)
        btn_cancel.pack(side=tk.RIGHT, padx=10)
        
        btn_restore = tk.Button(btn_frame, text="Confirm Restore", command=self.confirm_action, bg="#ffdddd", width=20)
        btn_restore.pack(side=tk.RIGHT, padx=10)

    def _populate_list(self):
        for mapping in self.restore_map.get("mappings", []):
            path = mapping["source_path"]
            if os.path.exists(path):
                status = "Exists (Will Overwrite)"
            else:
                status = "Will Create"
            self.tree.insert("", tk.END, values=(path, status))

    def confirm_action(self):
        self.destroy()
        self.on_confirm(self.zip_path, self.restore_map)


class BackupApp:
    def __init__(self, root):
        self.root = root
        self.manager = ConfigManager()
        
        self.root.title(f"DirBackup Utility {'(Admin)' if is_admin() else ''}")
        self.root.geometry("650x600")
        
        # UI Setup
        self._setup_ui()
        
        # Load initial data
        self.refresh_list()
        
        # Check Args for Auto-Restore
        self.check_cli_args()

    def check_cli_args(self):
        if len(sys.argv) > 1:
            potential_zip = sys.argv[1]
            if os.path.exists(potential_zip) and potential_zip.endswith(".zip"):
                self.root.after(500, lambda: self.process_restore_request(potential_zip))

    def _setup_ui(self):
        # --- Profile Frame ---
        prof_frame = tk.LabelFrame(self.root, text="Profile Management", padx=10, pady=5)
        prof_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(prof_frame, text="Profile:").pack(side=tk.LEFT)
        
        self.profile_var = tk.StringVar(value=self.manager.get_current_profile())
        self.combo_profile = ttk.Combobox(prof_frame, textvariable=self.profile_var, state="readonly")
        self.combo_profile['values'] = self.manager.get_profiles()
        self.combo_profile.bind("<<ComboboxSelected>>", self.on_profile_change)
        self.combo_profile.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        btn_new_prof = tk.Button(prof_frame, text="New", command=self.new_profile, width=8)
        btn_new_prof.pack(side=tk.LEFT, padx=2)
        
        btn_del_prof = tk.Button(prof_frame, text="Delete", command=self.delete_profile, width=8)
        btn_del_prof.pack(side=tk.LEFT, padx=2)

        # --- Top Frame: Actions ---
        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        btn_add = tk.Button(top_frame, text="Add Directory", command=self.add_directory, width=15)
        btn_add.pack(side=tk.LEFT, padx=5)

        btn_remove = tk.Button(top_frame, text="Remove Selected", command=self.remove_directory, width=15)
        btn_remove.pack(side=tk.LEFT, padx=5)

        # --- Middle Frame: List ---
        mid_frame = tk.Frame(self.root, padx=10, pady=5)
        mid_frame.pack(fill=tk.BOTH, expand=True)

        lbl_list = tk.Label(mid_frame, text="Directories in Current Profile:")
        lbl_list.pack(anchor=tk.W)

        self.dir_listbox = tk.Listbox(mid_frame, selectmode=tk.EXTENDED)
        self.dir_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = tk.Scrollbar(mid_frame, orient=tk.VERTICAL, command=self.dir_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.dir_listbox.config(yscrollcommand=scrollbar.set)

        # --- Backup Config Frame ---
        config_frame = tk.Frame(self.root, padx=10, pady=5)
        config_frame.pack(fill=tk.X)
        
        tk.Label(config_frame, text="Backup Name Tag (Optional):").pack(side=tk.LEFT)
        self.entry_name = tk.Entry(config_frame)
        self.entry_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # --- Bottom Frame: Execute ---
        bottom_frame = tk.Frame(self.root, padx=10, pady=15)
        bottom_frame.pack(fill=tk.X)

        btn_backup = tk.Button(bottom_frame, text="Update Backup (Create ZIP)", command=self.create_backup_thread, bg="#dddddd", height=2)
        btn_backup.pack(fill=tk.X, pady=5)

        btn_restore = tk.Button(bottom_frame, text="Restore Checkpoints (ZIP)", command=self.initiate_restore, bg="#dddddd", height=2)
        btn_restore.pack(fill=tk.X, pady=5)

        # --- Status Bar & Progress ---
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=2)
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # --- Profile Methods ---
    def on_profile_change(self, event):
        new_prof = self.profile_var.get()
        self.manager.set_current_profile(new_prof)
        self.refresh_list()

    def new_profile(self):
        name = simpledialog.askstring("New Profile", "Enter profile name:")
        if name:
            if name in self.manager.get_profiles():
                messagebox.showerror("Error", "Profile already exists.")
                return
            self.manager.add_profile(name)
            self.manager.set_current_profile(name)
            self.update_combo()
            self.refresh_list()

    def delete_profile(self):
        cur = self.manager.get_current_profile()
        if len(self.manager.get_profiles()) <= 1:
             messagebox.showwarning("Warning", "Cannot delete the last profile.")
             return
        
        if messagebox.askyesno("Delete Profile", f"Are you sure you want to delete profile '{cur}'?"):
            self.manager.delete_profile(cur)
            self.update_combo()
            self.refresh_list()

    def update_combo(self):
        self.combo_profile['values'] = self.manager.get_profiles()
        self.profile_var.set(self.manager.get_current_profile())

    def refresh_list(self):
        self.dir_listbox.delete(0, tk.END)
        for path in self.manager.get_paths():
            self.dir_listbox.insert(tk.END, path)

    # --- Directory Methods ---
    def add_directory(self):
        path = filedialog.askdirectory()
        if path:
            path = os.path.abspath(path)
            if path not in self.manager.get_paths():
                self.manager.add_path(path)
                self.dir_listbox.insert(tk.END, path)
            else:
                messagebox.showinfo("Info", "Directory already added.")

    def remove_directory(self):
        selected_indices = self.dir_listbox.curselection()
        # Get paths before deleting (indices shift)
        paths_to_remove = [self.dir_listbox.get(i) for i in selected_indices]
        
        for path in paths_to_remove:
            self.manager.remove_path(path)
        
        self.refresh_list()

    # --- Backup Methods ---
    def create_backup_thread(self):
        paths = self.manager.get_paths()
        if not paths:
            messagebox.showwarning("Warning", "No directories in this profile!")
            return

        # Smart Naming
        profile_name = self.manager.get_current_profile()
        tag = self.entry_name.get().strip()
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        if tag:
            default_name = f"{profile_name}_{tag}_{date_str}.zip"
        else:
            default_name = f"{profile_name}_{date_str}.zip"
            
        save_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            defaultextension=".zip", 
            filetypes=[("Zip Files", "*.zip")]
        )
        if not save_path:
            return

        threading.Thread(target=self.create_backup, args=(save_path, paths), daemon=True).start()

    def create_backup(self, save_path, paths):
        self.status_var.set("Backing up... Calculating files...")
        self.progress['value'] = 0
        try:
            # Phase 1: Count files
            total_files = 0
            for source_path in paths:
                if os.path.exists(source_path):
                     for _, _, files in os.walk(source_path):
                         total_files += len(files)
            
            self.progress['maximum'] = total_files if total_files > 0 else 1
            
            restore_map = {"mappings": []}
            processed_count = 0
            
            self.status_var.set(f"Backing up... (0/{total_files})")
            
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for idx, source_path in enumerate(paths):
                    if not os.path.exists(source_path):
                         # Skip missing, log it?
                         continue
                         
                    folder_name = os.path.basename(source_path)
                    archive_name = f"{folder_name}_{idx}" 
                    
                    restore_map["mappings"].append({
                        "source_path": source_path,
                        "archive_name": archive_name
                    })
                    
                    for root, dirs, files in os.walk(source_path):
                        for file in files:
                            abs_path = os.path.join(root, file)
                            rel_path = os.path.relpath(abs_path, source_path)
                            zip_path = os.path.join(archive_name, rel_path)
                            zipf.write(abs_path, zip_path)
                            
                            processed_count += 1
                            if processed_count % 5 == 0 or processed_count == total_files:
                                self.root.after(0, self.update_progress, processed_count, total_files)
                            
                zipf.writestr("restore_map.json", json.dumps(restore_map, indent=4))
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Backup created:\n{save_path}"))
            self.root.after(0, lambda: self.status_var.set("Backup Complete"))
            self.root.after(0, lambda: self.progress.stop())

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, lambda: self.status_var.set("Error during backup"))

    def update_progress(self, current, total):
        self.progress['value'] = current
        self.status_var.set(f"Processing... ({current}/{total})")

    # --- Restore Methods ---
    def initiate_restore(self):
        zip_path = filedialog.askopenfilename(filetypes=[("Zip Files", "*.zip")])
        if not zip_path:
            return
        
        self.process_restore_request(zip_path)

    def process_restore_request(self, zip_path):
        try:
             with zipfile.ZipFile(zip_path, 'r') as zipf:
                if "restore_map.json" not in zipf.namelist():
                     messagebox.showerror("Error", "Invalid backup file: restore_map.json missing.")
                     return
                
                restore_map_data = zipf.read("restore_map.json")
                restore_map = json.loads(restore_map_data)
                
                # Show Preview Dialog
                PreviewDialog(self.root, zip_path, restore_map, self.handle_restore_confirmation)

        except Exception as e:
             messagebox.showerror("Error", f"Could not read backup file: {e}")

    def handle_restore_confirmation(self, zip_path, restore_map):
        # Admin Check
        if not is_admin():
            if messagebox.askyesno("Admin Required", "Restoring files usually requires Admin privileges.\n\nRelaunch as Admin to proceed?"):
                self.relaunch_as_admin(zip_path)
            return

        # Start Restore Thread
        threading.Thread(target=self.execute_restore, args=(zip_path, restore_map), daemon=True).start()

    def relaunch_as_admin(self, zip_path):
        params = f'"{zip_path}"'
        try:
            if getattr(sys, 'frozen', False):
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            else:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{sys.argv[0]}" {params}', None, 1)
            self.root.quit()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to elevate privileges: {e}")

    def execute_restore(self, zip_path, restore_map):
        self.status_var.set("Restoring... Calculating...")
        self.progress['value'] = 0
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # Count total files to extract
                file_list = [m for m in zipf.namelist() if not m.endswith('/') and m != "restore_map.json"]
                total_files = len(file_list)
                self.progress['maximum'] = total_files if total_files > 0 else 1
                
                processed_count = 0
                
                for mapping in restore_map["mappings"]:
                    source_path = mapping["source_path"]
                    archive_name = mapping["archive_name"]
                    
                    os.makedirs(source_path, exist_ok=True)
                    
                    for member in zipf.namelist():
                        if member.startswith(archive_name + "/"):
                            rel_path = member[len(archive_name)+1:] 
                            if not rel_path: continue
                            
                            target_file_path = os.path.join(source_path, rel_path)
                            
                            if member.endswith('/'):
                                os.makedirs(target_file_path, exist_ok=True)
                            else:
                                target_dir = os.path.dirname(target_file_path)
                                os.makedirs(target_dir, exist_ok=True)
                                with zipf.open(member) as source, open(target_file_path, "wb") as target:
                                    shutil.copyfileobj(source, target)
                                
                                processed_count += 1
                                if processed_count % 5 == 0 or processed_count == total_files:
                                    self.root.after(0, self.update_progress, processed_count, total_files)

            self.root.after(0, lambda: messagebox.showinfo("Success", "Restore complete!"))
            self.root.after(0, lambda: self.status_var.set("Restore Complete"))
            self.root.after(0, lambda: self.progress.stop())
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, lambda: self.status_var.set("Error during restore"))

if __name__ == "__main__":
    root = tk.Tk()
    app = BackupApp(root)
    root.mainloop()
