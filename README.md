# Aplikasi Bel Sekolah

Sistem bel sekolah otomatis untuk Raspberry Pi dengan web interface, support playlist murottal, dan multi-folder sounds.

---

## Fitur Utama

### Audio System

- **MP3 & WAV Support** - Menggunakan mpg123/aplay (ringan)
- **Subfolder Support** - Organisir sounds dalam folder (bel/, murottal/, dll)
- **Playlist** - Play multiple files berurutan
- **Auto-Sync** - Scan folder & update database otomatis
- **Interrupt** - Bel prioritas lebih tinggi dari murottal

### Scheduler

- **Jadwal Otomatis** - Sesuai jadwal sekolah
- **Multi Kategori** - Normal, Ujian, Puasa
- **Priority System** - Interrupt murottal saat bel masuk

### Web Interface

- **Responsive** - Optimal untuk HP
- **Manage Sounds** - Upload, sync, organize dalam folder
- **Bulk Upload** - Drag-drop multiple files
- **Playlist Manager** - Kelola urutan murottal
- **Real-time Control** - Play/stop manual

### Deployment

- **One-Click Install** - Setup otomatis
- **Auto-Start** - Nyala otomatis saat boot
- **Systemd Service** - Production-ready

---

## Quick Start

### 1. Install (5 Menit)

```bash
cd ~
git clone https://github.com/iaiapps/school-bel-python-web.git bel
cd bel
sudo ./install.sh
```

### 2. Akses

Dari HP/Laptop:

```
http://[IP-RASPBERRY-PI]:5000
```

Login:

- Username: `admin`
- Password: `admin123`

### 3. Setup Awal

1. Upload Sounds - Menu Upload atau Manage Sounds
2. Buat Playlist - Menu Playlist (untuk murottal)
3. Buat Jadwal - Menu Jadwal Harian
4. Test Audio - Settings -> Audio -> Test

---

## Menu Web

| Menu              | Fungsi                                 |
| ----------------- | -------------------------------------- |
| Dashboard         | Overview, quick actions, status        |
| Upload Sound     | Upload single file                     |
| Manage Sounds    | Kelola folder, bulk upload, sync      |
| Playlist         | Playlist untuk murottal/audio sequence |
| Jadwal Harian    | Atur jadwal bel otomatis               |
| Riwayat          | Log aktivitas                          |
| Settings         | Audio, network, security               |

---

## Cara Pakai

### Upload Sounds (Banyak File)

Cara 1: Via Web (Manage Sounds)

1. Menu Manage Sounds
2. Upload -> Pilih folder (bel/, murottal/, dll)
3. Drag-drop multiple files (max 50)
4. Upload

Cara 2: Via SCP/USB + Sync

```bash
# Copy file ke folder
scp *.mp3 admin@[IP]:/home/admin/bel/sounds/bel/

# Sync via web
Manage Sounds -> Sync Folder -> Preview -> Sync Now
```

### Buat Playlist Murottal

1. Menu Playlist -> Buat Playlist Baru
2. Nama: "Murottal Pagi"
3. Kelola -> Tambah file dengan urutan
4. Save

### Buat Jadwal

1. Jadwal Harian -> Tambah Jadwal
2. Pilih: Hari, Waktu, Kegiatan
3. Pilih Sound:
   - Single file: bel/bell.mp3
   - Playlist: Murottal Pagi
4. Simpan

### Sync Sounds

Jika ada perubahan di folder sounds/:

1. Manage Sounds -> Sync Folder
2. Lihat preview (new, missing, unchanged)
3. Centang "Hapus file yang tidak ada"
4. Sync Now

---

## Struktur Folder

```
bel/
├── sounds/              # Audio files
│   ├── bell.mp3        # Root level
│   ├── bel/            # Bell sounds
│   │   ├── bell1.mp3
│   │   └── islamic.mp3
│   ├── murottal/       # Murottal files
│   │   ├── 01-Alfatihah.mp3
│   │   └── 02-Al-Ikhlas.mp3
│   └── doa/            # Doa files
├── install.sh          # Installer
├── manage.sh           # Management
├── cleanup.sh          # Cleanup/Uninstall
└── ...
```

---

## Command Management

### manage.sh

```bash
./manage.sh start      # Start manual
./manage.sh stop       # Stop
./manage.sh restart    # Restart
./manage.sh status     # Status
./manage.sh info       # Info akses & QR
./manage.sh logs       # Logs
```

### systemctl (Service)

```bash
sudo systemctl status bel-sekolah
sudo systemctl restart bel-sekolah
sudo journalctl -u bel-sekolah -f
```

---

## Settings

### Audio

- Volume: 0-100%
- Output: Auto/Headphone/HDMI
- Auto-restore: Volume tersimpan saat reboot

### Network

- Port: Default 5000
- Hostname: Menggunakan hostname asli RPi
- Access: Via IP atau hostname.local

### Security

- Ganti Password: Settings -> Security
- Session: 24 jam

---

## Troubleshooting

### Audio tidak keluar

```bash
# Install mpg123 (untuk MP3)
sudo apt install mpg123

# Test manual
mpg123 -q sounds/bel/bell.mp3

# Cek volume
alsamixer

# Restart service
sudo systemctl restart bel-sekolah
```

### Tidak bisa akses web

```bash
# Cek service
sudo systemctl status bel-sekolah

# Cek IP
hostname -I

# Cek firewall
sudo ufw allow 5000
```

### Database error

```bash
# Backup
cp database.db database.db.backup

# Reset
rm database.db
sudo systemctl restart bel-sekolah
```

---

## Database Schema

| Table            | Fungsi                          |
| ---------------- | ------------------------------- |
| sounds           | File audio (name, file_path)    |
| playlists        | Playlist header                 |
| playlist_items   | Urutan file dalam playlist      |
| schedules        | Jadwal bel                      |
| categories       | Kategori (normal, ujian, puasa) |
| history          | Log playback                    |
| users            | User login                      |
| app_settings     | Pengaturan aplikasi             |

---

## Development

### Requirements

- Python 3.8+
- Raspberry Pi OS
- mpg123, alsa-utils

### Setup Dev

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

### Testing

```bash
# Test audio
mpg123 -q sounds/test.mp3

# Test API
curl http://localhost:5000/api/core-status
```

---

## Changelog

### v3.0 (Current)

- Subfolder support untuk sounds
- Manage Sounds UI (bulk upload, sync)
- Playlist system
- Settings via database
- No pygame (mpg123/aplay)
- Responsive mobile UI
- Auto-sync sounds

### v2.0

- Playlist support
- Multi-category schedules
- Web interface improvement

### v1.0

- Basic scheduler
- Single file play

---

## Tips

1. Organisir sounds dalam folder - bel/, murottal/, doa/
2. Gunakan playlist untuk murottal - Lebih mudah manage
3. Backup database rutin - cp database.db backup/
4. Test sebelum schedule - Play manual dulu
5. Sync setelah copy file - Manage Sounds -> Sync

---

## License

Aplikasi ini dibuat untuk SDIT Harapan Umat Jember.

---

## Support

- Version: 3.0
- Platform: Raspberry Pi 3B+/4/5
- OS: Raspberry Pi OS
- Python: 3.8+

GitHub: https://github.com/iaiapps/school-bel-python-web

---

Developed by iaiapps | 2026
