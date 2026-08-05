# Changelog

## 2026-08-05 — Konsistensi UI/UX (tampilan saja, backend tidak disentuh)

### Template & Layout
- Tambah `templates/base.html` (head, header seragam, flash messages, blocks: title, header_title, styles, content, scripts)
- Konversi 11 template agar `extends base.html`: index, history, logs, upload, schedule, add_schedule, edit_schedule, settings, playlists, sounds (login tetap standalone karena layout full-screen, hanya disamakan font-nya)
- Header seragam `.app-header` di semua halaman (title + tombol settings/logout), tombol "Kembali" distandarkan ke `btn btn-sm btn-outline-secondary`

### Responsive & Mobile
- Fix bug `.mt-3` (salah property: margin-bottom → margin-top)
- Input form 15px → 16px (cegah auto-zoom iOS); login 14px → 16px
- Tambah `touch-action: manipulation` di tombol (hilangkan tap delay)
- Tambah `-webkit-tap-highlight-color: transparent`
- `col-md-4`/`col-md-6` tanpa `col-12` di playlists form, settings QR buttons, sounds stats/modal, folder structure, logs controls → ditambahkan `col-12` (mobile first)
- Hapus menu "Upload Sound" duplikat di index.html (deskripsi Kelola Sounds diperluas)

### Bahasa (seragam ke Bahasa Indonesia)
- sounds.html: Manage Sounds→Kelola Sounds, Sync→Sinkronkan, New Folder→Folder Baru, Folder Structure→Struktur Folder, All Sounds→Semua Sounds, dan semua string JS (alert, confirm, status)
- history.html: Bell History→Riwayat Bel, Bersihkan History→Bersihkan Riwayat
- logs.html: System Logs→Log Sistem, Refresh→Muat Ulang, Download→Unduh, 50 Lines→50 Baris
- index.html: Manage Sounds→Kelola Sounds, sequence→urutan
- playlists.html: Loading...→Memuat...

### Typography
- Google Fonts: Poppins (heading/menu-title/card-header) + Open Sans (body), termasuk login.html
- CSS: heading pakai Poppins via rule h1-h6/.menu-title/.card-header/.app-header-title

### Perbaikan di sini
- Backup: `git diff` (file: templates/*.html, static/css/style.css) — backend (web.py routes, core.py, database.py, sounds_manager.py) TIDAK diubah

## 2026-08-05 — Design System Bersih (Paket A)

### Flat Colors (gradien dihilangkan)
- `quick-action-btn`, `time-badge`, `.navbar`, `.folder-header` (sounds.html), `btn-login` (login.html): gradien oranye → solid `#ff5722`; hover `#e64a19`
- Hover kartu: dari translateX/translateY + shadow tebal → background tint `#fff7f0` halus
- Login body: gradien → solid oranye

### Card & Komponen Seragam
- `.status-card`/`.dashboard-card`/`.menu-card`/`.schedule-item`: radius 12px, shadow layered lembut (0 1px 2px + 0 1px 3px)
- Bootstrap `.card`: border `#eceef1` tipis, radius 12px, header/footer putih bersih
- Outline buttons: border 2px → 1px
- Form control: border 2px → 1px `#e0e3e7`, focus ring lebih lembut

### Tabel Bersih
- `table-bordered` dihapus dari upload.html & schedule.html
- `.table`: padding sel 12px 14px, header th lebih tinggi hurufnya + border halus `#e5e7eb`, border tabel `#f0f2f4`

### Verifikasi
- Semua 10 halaman render 200 OK; CSS braces balanced; 0 gradien tersisa

## 2026-08-05 — Hapus Route Orphan /upload (backend web.py)

- Hapus route `/upload` (GET+POST) dan `/delete_sound/<id>` dari web.py (endpoint `upload`, `delete_sound`)
- Hapus `templates/upload.html`
- Route `/download/sound/<id>` dipertahankan (dipakai sounds.html), redirect error-nya diubah `url_for("upload")` → `url_for("sounds_page")`
- Verifikasi: /upload → 404, semua halaman render 200 OK, download redirect ke /sounds
- CATATAN: ini satu-satunya perubahan yang menyentuh backend (web.py) selama sesi — selain itu semua hanya templates + CSS

## 2026-08-05 — Fix 5 Bug Kritis (hasil audit code-review)

1. Ganti password 500: tambah field `current_password` di settings.html + guard kosong di `settings_password()` (web.py)
2. Open redirect login: validasi `next` hanya path internal (startswith `/` dan bukan `//`) — web.py:136-137
3. `int()` crash: `settings_network` port (1-65535) dan `settings_audio` volume (0-100) divalidasi `isdigit` + range sebelum int()
4. `/api/next-bell` bocorkan jadwal kategori non-aktif: tambah filter `category = active_category` (konsisten dengan index() dan core.py)
5. Download sound subfolder rusak: ganti `secure_filename` (yang menghancurkan path `bell/shift.wav`) dengan validasi realpath dalam UPLOAD_FOLDER + `send_from_directory` pakai path asli; traversal `../` ditolak

Verifikasi: password ganti OK + rollback, evil.com/`//evil.com` → `/`, internal `/schedule` OK, port/volume non-angka → flash bukan 500, download subfolder → 200, traversal → 302, regresi 10 halaman ALL 200.
