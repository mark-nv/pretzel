import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import time

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
DRIVE_FOLDER_NAME = 'dolphypretzel'

def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def get_or_create_folder(service, folder_name):
    query = f"name='{folder_name}' mimeType='application/vnd.google-apps.folder'"
    response = service.files().list(q=query, spaces='drive').execute()
    folders = response.get('files', [])
    if folders:
        return folders[0]['id']
    folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder['id']

# Local storage setup
HOME_DIR = os.path.expanduser("~/Documents/dolphypretzel")
SHARED_DIR = os.path.join(HOME_DIR, "shared")
if not os.path.exists(HOME_DIR):
    os.makedirs(HOME_DIR)
if not os.path.exists(SHARED_DIR):
    os.makedirs(SHARED_DIR)

# Main app window
root = tk.Tk()
root.title("dolphypretzel")
root.geometry("500x400")

# Variables
entries = []
image_path = tk.StringVar()
last_check = time.time()

# Functions
def save_entry():
    text = text_entry.get("1.0", tk.END).strip()
    if not text:
        messagebox.showwarning("Warning", "Please enter some text!")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    entry_file = f"{HOME_DIR}/entry_{timestamp}.txt"
    
    with open(entry_file, "w") as f:
        f.write(text)
    
    if image_path.get():
        image_dest = f"{HOME_DIR}/entry_{timestamp}{os.path.splitext(image_path.get())[1]}"
        shutil.copy(image_path.get(), image_dest)
    
    sync_to_drive(entry_file)
    text_entry.delete("1.0", tk.END)
    image_path.set("")
    update_entry_list()

def send_entry():
    selected = entry_list.curselection()
    if not selected:
        messagebox.showwarning("Warning", "Select an entry to send!")
        return
    entry_file = f"{HOME_DIR}/{entries[selected[0]]}"
    shutil.copy(entry_file, SHARED_DIR)
    base_name = entry_file.replace(".txt", "")
    for ext in [".png", ".jpg", ".jpeg", ".gif"]:
        if os.path.exists(base_name + ext):
            shutil.copy(base_name + ext, SHARED_DIR)
    sync_to_drive(entry_file, shared=True)
    messagebox.showinfo("Sent", "Entry sent to shared folder!")

def add_image():
    file = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif")])
    if file:
        image_path.set(file)

def update_entry_list():
    entry_list.delete(0, tk.END)
    entries.clear()
    for file in os.listdir(HOME_DIR):
        if file.endswith(".txt") and not file.startswith("shared_"):
            entries.append(file)
            entry_list.insert(tk.END, file.replace("entry_", "").replace(".txt", ""))
    check_shared_entries()

def view_entry():
    selected = entry_list.curselection()
    if not selected:
        return
    entry_file = f"{HOME_DIR}/{entries[selected[0]]}"
    with open(entry_file, "r") as f:
        text_entry.delete("1.0", tk.END)
        text_entry.insert(tk.END, f.read())
    base_name = entry_file.replace(".txt", "")
    for ext in [".png", ".jpg", ".jpeg", ".gif"]:
        if os.path.exists(base_name + ext):
            image_path.set(base_name + ext)
            break
    else:
        image_path.set("")

def sync_to_drive(file_path, shared=False):
    service = get_drive_service()
    folder_id = get_or_create_folder(service, DRIVE_FOLDER_NAME)
    file_name = os.path.basename(file_path)
    if shared:
        file_name = f"shared_{file_name}"
    media = MediaFileUpload(file_path)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

def check_shared_entries():
    global last_check
    service = get_drive_service()
    folder_id = get_or_create_folder(service, DRIVE_FOLDER_NAME)
    query = f"'{folder_id}' in parents"
    response = service.files().list(q=query).execute()
    for file in response.get('files', []):
        if file['name'].startswith("shared_") and not os.path.exists(f"{SHARED_DIR}/{file['name']}"):
            file_data = service.files().get_media(fileId=file['id']).execute()
            local_path = f"{SHARED_DIR}/{file['name']}"
            with open(local_path, 'wb') as f:
                f.write(file_data)
            shutil.move(local_path, f"{HOME_DIR}/{file['name'].replace('shared_', '')}")
            messagebox.showinfo("New Entry", f"Received: {file['name'].replace('shared_', '')}")
    update_entry_list()
    last_check = time.time()
    root.after(5000, check_shared_entries)  # Check every 5 seconds

# UI Elements
text_entry = tk.Text(root, height=10, width=50)
text_entry.pack(pady=10)

image_label = tk.Label(root, textvariable=image_path, wraplength=400)
image_label.pack()

button_frame = tk.Frame(root)
button_frame.pack(pady=5)
tk.Button(button_frame, text="Add Image", command=add_image).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="Save Entry", command=save_entry).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="Send Entry", command=send_entry).pack(side=tk.LEFT, padx=5)

entry_list = tk.Listbox(root, height=10, width=50)
entry_list.pack(pady=10)
entry_list.bind("<<ListboxSelect>>", lambda e: view_entry())

# Initial setup
update_entry_list()
root.after(5000, check_shared_entries)  # Start periodic sync check

# Run the app
root.mainloop()