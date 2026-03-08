# 🔔 Aplikasi Bel Sekolah

Aplikasi bel sekolah otomatis berbasis web untuk **Raspberry Pi** dengan support playlist murottal.

## ✨ Fitur Utama

### 🎵 Audio System
- ✅ **Support MP3 & WAV** - Gunakan file audio format apapun
- ✅ **Ringan** - Tidak pakai pygame, hanya mpg123 (150KB)
- ✅ **Playlist Murottal** - Putar banyak file berurutan
- ✅ **Interrupt** - Bel masuk otomatis stop murottal
- ✅ **Manual Play & Stop** - Kontrol dari web

### 📅 Scheduler
- ✅ **Jadwal Otomatis** - Sesuaikan dengan jadwal sekolah
- ✅ **Multi Kategori** - Normal, Ujian, Puasa, dll
- ✅ **Interrupt Priority** - Bel lebih prioritas dari murottal

### 🌐 Web Interface
- ✅ **Akses dari HP** - Kontrol via WiFi lokal
- ✅ **Responsive** - Tampilan mobile-friendly
- ✅ **Easy Upload** - Upload sound langsung dari web
- ✅ **History Log** - Lihat riwayat bel dimainkan

### 🚀 Deployment
- ✅ **1-Click Install** - Setup otomatis dengan systemd
- ✅ **Auto Start** - Nyala otomatis saat boot
- ✅ **QR Code** - Scan untuk akses cepat
- ✅ **No Hostname Change** - Aman untuk sistem

---

## 🚀 Quick Start

### 1. Install (5 menit)

```bash
cd /home/pi/bel_sekolah
sudo ./install.sh
```

**Tunggu sampai selesai** - Installer akan:
- Install dependencies (mpg123, alsa-utils)
- Setup virtual environment
- Install Python packages
- Initialize database
- Create systemd service
- Generate QR code

### 2. Akses dari HP

**Cara 1: Scan QR Code**
- Setelah install, QR code muncul di terminal
- Scan dengan HP → Langsung terbuka

**Cara 2: Manual**
```bash
./manage.sh info
# Lihat IP address: http://192.168.x.x:5000
```

**Login Default:**
- Username: `admin`
- Password: `admin123`

---

## 📱 Cara Pakai

### Upload Sound (Pertama Kali)

1. **Menu Upload Sound**
2. Upload file MP3/WAV (bell.mp3, murottal01.mp3, dll)
3. Beri nama yang mudah dikenali

### Buat Playlist Murottal

1. **Menu Playlist** → **Buat Playlist Baru**
2. Nama: "Murottal Pagi", Deskripsi: "Murottal untuk pagi"
3. **Kelola** → Tambah file satu per satu
4. Urutkan sesuai keinginan (Al-Fatihah, Yasin, dll)

### Buat Jadwal Bel

1. **Menu Jadwal Harian** → **Tambah Jadwal**
2. Pilih: Hari, Waktu, Nama Kegiatan
3. **Pilih Sound**:
   - 🔊 **Single File**: bell.mp3 (untuk bel pendek)
   - 📋 **Playlist**: Murottal Pagi (untuk murottal panjang)
4. Simpan

### Test Audio

1. **Menu Pengaturan** → Tab **Audio**
2. Atur volume slider
3. Klik **Test Audio**

---

## 🎮 Command Management

### manage.sh

```bash
./manage.sh start      # Start aplikasi (manual)
./manage.sh stop       # Stop aplikasi
./manage.sh restart    # Restart aplikasi
./manage.sh status     # Cek status
./manage.sh info       # Info akses & QR code
./manage.sh logs       # Lihat log
```

### systemctl (Production)

```bash
sudo systemctl status bel-sekolah    # Status
sudo systemctl restart bel-sekolah   # Restart
sudo systemctl stop bel-sekolah      # Stop
sudo journalctl -u bel-sekolah -f    # Live logs
```

---

## 📊 Struktur Database

### Tables:
- **sounds** - File audio yang diupload
- **playlists** - Playlist untuk murottal
- **playlist_items** - Urutan file dalam playlist
- **schedules** - Jadwal bel
- **categories** - Kategori jadwal (normal, ujian, puasa)
- **history** - Log aktivitas
- **users** - User login
- **app_settings** - Pengaturan aplikasi

### Playlist Format:
Di database `schedules.sound_file`:
- Single file: `bell.mp3`
- Playlist: `playlist:5` (ID playlist)

---

## ⚙️ Settings

### Audio Settings
- **Output**: Auto / Headphone / HDMI
- **Volume**: 0-100%
- **Apply**: Otomatis saat save

### Network Settings
- **Port**: Default 5000
- **Hostname**: Menggunakan hostname asli Raspberry Pi (tidak diubah)
- **Static IP**: Opsional

### Security
- **Ganti Password**: Settings → Security
- **Session**: 24 jam
- **Login Required**: Semua halaman butuh login

---

## 🔧 Troubleshooting

### Audio tidak keluar

```bash
# Cek volume
alsamixer

# Test manual
mpg123 -q sounds/bell.mp3
aplay sounds/bell.wav

# Restart service
sudo systemctl restart bel-sekolah
```

### Tidak bisa akses dari HP

1. **Cek WiFi**: HP dan Raspberry Pi di jaringan sama
2. **Cek IP**: `hostname -I`
3. **Cek Service**: `sudo systemctl status bel-sekolah`
4. **Cek Firewall**: `sudo ufw allow 5000`

### Service error

```bash
# Lihat log
sudo journalctl -u bel-sekolah -n 50

# Re-install
sudo ./cleanup.sh
sudo ./install.sh
```

### Database error

```bash
# Reset database (HAPUS SEMUA DATA!)
cp database.db database.db.backup
rm database.db
python3 -c "from database import init_db; init_db()"
```

---

## 📁 Struktur File

```
bel_sekolah/
├── install.sh          ⭐ Installer otomatis
├── manage.sh           ⭐ Management script
├── cleanup.sh          ⭐ Cleanup untuk fresh install
├── uninstall.sh        ⭐ Uninstall
├── run.py              Entry point aplikasi
├── web.py              Flask web server
├── core.py             Scheduler & audio player
├── database.py         Database functions
├── settings.py         Settings manager
├── config.py           Configuration
├── requirements.txt    Python dependencies
├── database.db         SQLite database (PENTING!)
├── sounds/             File audio MP3/WAV
├── templates/          HTML templates
└── static/             CSS/JS assets
```

---

## 🔐 Security

### Default Credentials
- **Username**: admin
- **Password**: admin123

### ⚠️ PENTING!
**Ganti password setelah install pertama kali!**

### Network Security
- **Bind Address**: 0.0.0.0 (semua interface)
- **Port**: 5000 (configurable)
- **HTTPS**: Belum (untuk lokal network)
- **Recommendation**: Gunakan WiFi dengan password

---

## 📦 Backup & Restore

### Backup Data Penting

```bash
# Backup database
cp database.db database.db.backup.$(date +%Y%m%d)

# Backup sounds
tar -czf sounds.backup.$(date +%Y%m%d).tar.gz sounds/

# Backup semua settings
./manage.sh info > system.info.txt
```

### Restore

```bash
# Stop service
sudo systemctl stop bel-sekolah

# Restore database
cp database.db.backup database.db

# Restore sounds
tar -xzf sounds.backup.tar.gz -C .

# Start service
sudo systemctl start bel-sekolah
```

---

## 🛠️ Development

### Requirements
- Python 3.8+
- Raspberry Pi OS (32/64 bit)
- mpg123
- alsa-utils

### Setup Development

```bash
# Install dependencies
sudo apt install mpg123 alsa-utils python3-venv

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt

# Run
python3 run.py
```

### Testing Audio

```bash
# Test dari command line
mpg123 -q sounds/test.mp3

# Test API
curl -X POST http://localhost:5000/api/test-audio
```

---

## 📋 Changelog

### Version 3.0 (Current)
- ✅ Hapus pygame, ganti mpg123/aplay
- ✅ Playlist system untuk murottal
- ✅ Settings pakai database (bukan JSON)
- ✅ Stop audio manual dari web
- ✅ No hostname change (aman)
- ✅ Hapus migrations (fresh install)

### Version 2.0
- Playlist support
- Multi category
- Web interface improvement

### Version 1.0
- Basic scheduler
- Single file play
- Web interface

---

## 💡 Tips & Best Practices

### Audio
1. **Gunakan MP3** untuk file kecil & kualitas baik
2. **Normalize volume** semua file sebelum upload
3. **Test dulu** sebelum buat jadwal

### Playlist
1. **Beri nama jelas**: "Murottal Pagi", "Murottal Sore"
2. **Urutkan file**: 01-Alfatihah.mp3, 02-Al-Ikhlas.mp3
3. **Test playlist**: Pastikan urutan benar

### Schedule
1. **Backup jadwal** sebelum edit besar
2. **Test interrupt**: Pastikan bel prioritas tinggi
3. **Kategori**: Pakai untuk jadwal khusus (ujian, puasa)

### Maintenance
1. **Backup rutin**: Database & sounds
2. **Cek log**: Minimal sekali seminggu
3. **Update**: Backup dulu sebelum update

---

## 🤝 Support

### Informasi
- **Version**: 3.0
- **Platform**: Raspberry Pi (3B+, 4, 5)
- **OS**: Raspberry Pi OS
- **Python**: 3.8+

### Kontak
Untuk pertanyaan atau issue, silakan hubungi tim IT sekolah.

---

## 📄 License

Aplikasi ini dibuat khusus untuk **SDIT Harapan Umat Jember**.

---

## 🙏 Credits

Developed with ❤️ for Islamic Education

**Version 3.0** | **2026**
