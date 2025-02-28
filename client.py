import tkinter as tk
from tkinter import ttk, messagebox
import os
import webview

# IP kayıtlarının tutulacağı dosya
IP_FILE = 'saved_ips.txt'

def load_saved_ips():
    """Dosyadan daha önce kaydedilmiş IP adreslerini yükler."""
    if os.path.exists(IP_FILE):
        with open(IP_FILE, 'r') as f:
            ips = f.read().splitlines()
            return ips
    return []

def save_ip(ip, ips_list):
    """Girilen IP kaydedilmemişse listeye ekleyip dosyaya yazar."""
    if ip not in ips_list:
        ips_list.append(ip)
        with open(IP_FILE, 'w') as f:
            for ip_addr in ips_list:
                f.write(ip_addr + "\n")

def remove_ip():
    """Combobox'tan seçili IP adresini listeden kaldırır ve dosyayı günceller."""
    selected_ip = combo.get().strip()
    if selected_ip in saved_ips:
        if messagebox.askyesno("Onay", f"{selected_ip} adresini silmek istediğinize emin misiniz?"):
            saved_ips.remove(selected_ip)
            with open(IP_FILE, 'w') as f:
                for ip_addr in saved_ips:
                    f.write(ip_addr + "\n")
            combo['values'] = saved_ips
            entry.delete(0, tk.END)
            if saved_ips:
                entry.insert(0, saved_ips[0])
            else:
                entry.insert(0, "localhost:5000")

def connect():
    """Girilen IP adresine göre PyWebView penceresi açar ve IP'yi kaydeder."""
    ip_input = entry.get().strip()
    # http:// veya https:// eklenmemişse otomatik ekle
    if not ip_input.startswith("http://") and not ip_input.startswith("https://"):
        ip_input = "http://" + ip_input
    # Girilen değeri dosyaya kaydet
    save_ip(entry.get().strip(), saved_ips)
    # WebView penceresini oluştur
    webview.create_window("Discord Benzeri Chat Client", ip_input)
    root.destroy()
    webview.start()

def on_combobox_select(event):
    """Combobox'tan seçilen IP'yi entry alanına aktarır."""
    selected_ip = combo.get()
    entry.delete(0, tk.END)
    entry.insert(0, selected_ip)

# Tkinter arayüzünü oluştur
root = tk.Tk()
root.title("Sunucu IP / URL Giriniz")

# Daha önce kaydedilmiş IP'leri yükle
saved_ips = load_saved_ips()

label = tk.Label(root, text="Sunucu IP adresini veya URL'sini giriniz:")
label.pack(padx=10, pady=5)

# Kaydedilmiş IP adreslerinin listelendiği Combobox
combo_label = tk.Label(root, text="Önceden girilmiş IP'ler:")
combo_label.pack(padx=10, pady=5)

combo = ttk.Combobox(root, values=saved_ips, state="readonly", width=37)
combo.pack(padx=10, pady=5)
combo.bind("<<ComboboxSelected>>", on_combobox_select)

# IP girişi için Entry alanı
entry = tk.Entry(root, width=40)
entry.pack(padx=10, pady=5)
if saved_ips:
    entry.insert(0, saved_ips[0])
else:
    entry.insert(0, "localhost:5000")

# Butonlar
button_frame = tk.Frame(root)
button_frame.pack(padx=10, pady=10)

connect_btn = tk.Button(button_frame, text="Bağlan", command=connect)
connect_btn.grid(row=0, column=0, padx=5)

remove_btn = tk.Button(button_frame, text="Seçileni Sil", command=remove_ip)
remove_btn.grid(row=0, column=1, padx=5)

root.mainloop()
