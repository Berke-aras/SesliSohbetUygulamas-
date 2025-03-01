import tkinter as tk
from tkinter import ttk, messagebox
import os
import webview

# Tema renkleri
BG_COLOR = "#36393f"
TEXT_COLOR = "#dcddde"
INPUT_BG = "#40444b"
BUTTON_BG = "#5865f2"
HOVER_COLOR = "#4752c4"
BORDER_COLOR = "#202225"

# IP kayıtlarının tutulacağı dosya
IP_FILE = 'saved_ips.txt'

def load_saved_ips():
    if os.path.exists(IP_FILE):
        with open(IP_FILE, 'r') as f:
            return f.read().splitlines()
    return []

saved_ips = load_saved_ips()

def save_ip(ip, ips_list):
    if ip not in ips_list:
        ips_list.append(ip)
        with open(IP_FILE, 'w') as f:
            f.write("\n".join(ips_list))

def remove_ip():
    selected_ip = combo.get().strip()
    if selected_ip in saved_ips:
        if messagebox.askyesno("Onay", f"{selected_ip} adresini silmek istediğinize emin misiniz?"):
            saved_ips.remove(selected_ip)
            with open(IP_FILE, 'w') as f:
                f.write("\n".join(saved_ips))
            combo['values'] = saved_ips
            entry.delete(0, tk.END)
            entry.insert(0, saved_ips[0] if saved_ips else "localhost:5000")

def connect():
    ip_input = entry.get().strip()
    if not ip_input.startswith(("http://", "https://")):
        ip_input = f"http://{ip_input}"
    save_ip(entry.get().strip(), saved_ips)
    webview.create_window("Discord Benzeri Chat Client", ip_input)
    root.destroy()
    webview.start()

def on_hover(e):
    e.widget['background'] = HOVER_COLOR

def on_leave(e):
    e.widget['background'] = BUTTON_BG

# Tkinter temasını özelleştirme
root = tk.Tk()
root.title("Sunucu Bağlantısı")
root.configure(bg=BG_COLOR)
root.geometry("500x400")
root.resizable(False, False)

style = ttk.Style()
style.theme_create("discord", settings={
    "TCombobox": {
        "configure": {
            "fieldbackground": INPUT_BG,
            "background": INPUT_BG,
            "foreground": TEXT_COLOR,
            "selectbackground": BORDER_COLOR,
            "selectforeground": TEXT_COLOR,
            "arrowcolor": TEXT_COLOR,
            "bordercolor": BORDER_COLOR,
            "lightcolor": BORDER_COLOR,
            "darkcolor": BORDER_COLOR
        }
    }
})
style.theme_use("discord")

# Ana frame
main_frame = tk.Frame(root, bg=BG_COLOR)
main_frame.pack(pady=30, padx=20, fill='both', expand=True)

# Başlık
title_label = tk.Label(
    main_frame,
    text="SUNUCU BAĞLANTISI",
    font=('Arial', 16, 'bold'),
    fg=TEXT_COLOR,
    bg=BG_COLOR
)
title_label.pack(pady=10)

# IP Seçim Combobox
combo_frame = tk.Frame(main_frame, bg=BG_COLOR)
combo_frame.pack(pady=10)

combo_label = tk.Label(
    combo_frame,
    text="Kayıtlı Sunucular:",
    font=('Arial', 10),
    fg=TEXT_COLOR,
    bg=BG_COLOR
)
combo_label.pack(anchor='w')

combo = ttk.Combobox(
    combo_frame,
    values=load_saved_ips(),
    font=('Arial', 10),
    width=30,
    state="readonly"
)
combo.pack(pady=5)
combo.bind("<<ComboboxSelected>>", lambda e: entry.delete(0, tk.END) or entry.insert(0, combo.get()))

# IP Giriş Alanı
entry_frame = tk.Frame(main_frame, bg=BG_COLOR)
entry_frame.pack(pady=10)

entry_label = tk.Label(
    entry_frame,
    text="Yeni Sunucu Adresi:",
    font=('Arial', 10),
    fg=TEXT_COLOR,
    bg=BG_COLOR
)
entry_label.pack(anchor='w')

entry = tk.Entry(
    entry_frame,
    font=('Arial', 10),
    bg=INPUT_BG,
    fg=TEXT_COLOR,
    insertbackground=TEXT_COLOR,
    relief='flat',
    width=35
)
entry.pack(pady=5, ipady=5)
entry.insert(0, "localhost:5000")

# Butonlar
button_frame = tk.Frame(main_frame, bg=BG_COLOR)
button_frame.pack(pady=20)

connect_btn = tk.Button(
    button_frame,
    text="Bağlan",
    command=connect,
    bg=BUTTON_BG,
    fg=TEXT_COLOR,
    activebackground=HOVER_COLOR,
    activeforeground=TEXT_COLOR,
    relief='flat',
    font=('Arial', 10, 'bold'),
    padx=20,
    pady=8
)
connect_btn.grid(row=0, column=0, padx=10)
connect_btn.bind("<Enter>", on_hover)
connect_btn.bind("<Leave>", on_leave)

remove_btn = tk.Button(
    button_frame,
    text="Sil",
    command=remove_ip,
    bg=INPUT_BG,
    fg=TEXT_COLOR,
    activebackground=HOVER_COLOR,
    activeforeground=TEXT_COLOR,
    relief='flat',
    font=('Arial', 10),
    padx=15,
    pady=6
)
remove_btn.grid(row=0, column=1, padx=10)
remove_btn.bind("<Enter>", lambda e: remove_btn.config(bg=BUTTON_BG))
remove_btn.bind("<Leave>", lambda e: remove_btn.config(bg=INPUT_BG))

root.mainloop()