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

## 2026-08-06 — Security & Bugfix Pass (hasil audit code-review)

### Critical
- C1 (core.py): race double-bell — `last_played` check+add kini atomik dalam satu lock, add SEBELUM play; hapus add pasca-play di main loop.
- C4 (web.py): open redirect login ditutup pakai `urlparse` — hanya path relatif tanpa scheme/netloc/`//` yang diikuti.
- C5 (web.py): `settings_password` — validasi field wajib sebelum `len()` -> tidak 500 lagi.

### Important
- I1: CSRF protection global (@before_request) — cek Origin/Referer utk POST/PUT/DELETE/PATCH; request non-browser tetap diizinkan.
- I2: `api_upload_sounds` — `rel_path` kini pakai `secure_filename(folder)`, bukan input mentah; + limit 10MB/file.
- I3: `bel_sekolah.db` di-untrack (git rm --cached) + masuk .gitignore.
- I4: login.html — h3->h1, autofocus dihapus, placeholder pakai ….
- I5: login.html — kredensial default (admin/admin123) dihapus dari halaman.
- I6: /api/logs & download — `lines` diparse+clamp 1..5000.
- I7: restart service — sudo -n + timeout=15 + pesan error lebih jelas.

### Suggestions (dieksekusi)
- except: -> except Exception: (inject_app_name).
- Dead branch if/else flash di add_schedule digabung.
- transition: all -> properti eksplisit (style.css x2, settings.html).
- playlists.html: hilangkan semua onclick= — addMultipleBtn id+listener; tombol hapus item data-remove-item + delegation; escapeHtml pada item.name, s.file_name, duration_formatted.

### Verifikasi
- 32/32 smoke test lulus (render 7 route, CSRF, open redirect 7 varian, C5, I6, I2, C1, I7, jinja 13 template).
- git status: 8 file berubah + D bel_sekolah.db (staged). BELUM di-commit.

## 2026-08-06 — Round 2: XSS Fixes + Mobile-First + A11y (hasil audit kedua)

### Critical (XSS — inline JS / innerHTML)
- K1 (index.html): XSS reflected via `onclick="switchCategory('{{ cat[1] }}')"` — Jinja autoescape tidak melindungi inline JS (entity `&#39;` di-decode HTML parser). Ganti ke `data-category="{{ cat[1] }}"` + `addEventListener`; `id` pakai `loop.index`.
- K2 (sounds.html): pratinjau sinkronisasi — `file/folder name` dari disk dirender mentah di innerHTML → `escapeHtml(f)`.
- K3 (sounds.html): dropdown folder `<option value="${f}">` → `escapeHtml(f)`.
- K4 (playlists.html): preview rebuild `item.name` mentah → `escapeHtml(item.name)` + `escapeHtml(total_duration_formatted)`.
- Bonus: sounds.html upload preview `file.name` → `escapeHtml`; logs.html `data.message`/`err` → `escapeHtml`.

### Mobile-First
- P1 (settings.html): sidebar nav-pills 6 item vertikal menumpuk di mobile → pill horizontal scroll (media query max-767.98px).
- P2 (schedule.html/history.html): kolom sekunder (Sound, Kategori, Hari, File) disembunyikan di layar kecil via `d-none d-md-table-cell`.

### A11y & Copy
- P3 (base.html): skip-to-content link "Lewati ke konten" → `#mainContent`.
- P4 (index.html): 4 icon menu dashboard diberi `aria-hidden="true"`.
- P5 (style.css): `.tabular-nums` (font-variant-numeric) — class dipakai schedule.html tapi tidak terdefinisi.
- P6: bare `except:` → `except Exception:` (core.py x2, settings.py x2); core.py:195 kini mencatat error, tidak swallow diam-diam.
- P7 (web.py): 14 pesan API Inggris → Indonesia (Failed to get logs, Folder name required, No files selected, dll).
- S1: `import subprocess`/`shutil` dari dalam fungsi → header web.py.
- S2: dead CSS `.navbar`, `.navbar-brand`, `.bg-white.p-3` dihapus (tidak dipakai template mana pun).
- S3: copy — "Bell Application"→"Aplikasi Bel Sekolah", "Waktu System"→"Waktu Sistem", "Memuat..."→"Memuat…" (index, sounds, logs).
- S4: `aria-live="polite"` pada #coreStatus dan #nextBell.

### Verifikasi
- Smoke test 39/39: render 8 halaman (login required), XSS marker 5x, API inti 4x + kategori, CSRF (Origin beda host 403 / Referer sesuai 200), open redirect 7 varian (semua netloc kosong) + next internal OK, C1 atomic (call#1 jadwal, call#2 None), login salah tidak 500, scan 200, skip link + aria-live + tabular-nums, pesan API Indonesia.
- `git add -A` dry-run: TIDAK ada *.db — database.db gitignored, bel_sekolah.db terhapus dari repo.
- Python py_compile OK, 13 template Jinja compile OK.
- BELUM di-commit (menunggu konfirmasi user sebelum push).
