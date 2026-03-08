from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os
import sqlite3
import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from database import init_db, get_history, clear_history, get_user_by_username, get_user_by_id
from database import get_all_categories, get_active_category, set_active_category, add_category, delete_category, get_schedules_by_category
from database import get_all_playlists, get_playlist, get_playlist_items, get_playlist_sound_files
from database import add_playlist, update_playlist, delete_playlist, add_playlist_item, remove_playlist_item, reorder_playlist_items
from config import Config
import core
import threading
from settings import settings_manager, get_all_settings, update_settings, get_setting
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config.from_object(Config)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'warning'

# User class untuk Flask-Login
class User(UserMixin):
    def __init__(self, id, username, is_active=True):
        self.id = id
        self.username = username
        self.active = is_active
    
    def is_active(self):
        return self.active

@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(int(user_id))
    if user_data:
        return User(user_data[0], user_data[1], user_data[3])
    return None

# ───── MAP HARI ─────
HARI_MAP = {
    "Monday": "Senin",
    "Tuesday": "Selasa",
    "Wednesday": "Rabu",
    "Thursday": "Kamis",
    "Friday": "Jumat",
    "Saturday": "Sabtu",
    "Sunday": "Minggu"
}

def _connect():
    conn = sqlite3.connect(Config.DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

# ───── LOGIN & LOGOUT ─────
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        if not username or not password:
            flash("Username dan password wajib diisi.", "error")
            return redirect(url_for("login"))
        
        user_data = get_user_by_username(username)
        if user_data and check_password_hash(user_data[2], password):
            if user_data[3]:  # is_active
                user = User(user_data[0], user_data[1], user_data[3])
                login_user(user, remember=True)
                flash(f"Selamat datang, {username}!", "success")
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for("index"))
            else:
                flash("Akun Anda tidak aktif.", "error")
        else:
            flash("Username atau password salah.", "error")
        
        return redirect(url_for("login"))
    
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Anda telah logout.", "info")
    return redirect(url_for("login"))

# ───── HALAMAN UTAMA (jadwal hari ini) ─────
@app.route("/")
@login_required
def index():
    today_eng = datetime.datetime.now().strftime("%A")
    hari_ini = HARI_MAP.get(today_eng, today_eng)
    now_time = datetime.datetime.now().strftime("%H:%M")

    # Get active category
    active_cat = get_active_category()
    active_category = active_cat[1] if active_cat else 'normal'
    categories = get_all_categories()

    with _connect() as conn:
        cur = conn.cursor()
        # ambil jadwal hari ini berdasarkan kategori aktif
        cur.execute("""
            SELECT time, activity, sound_file
            FROM schedules
            WHERE day_of_week = ? AND category = ?
            ORDER BY time
        """, (hari_ini, active_category))
        jadwal_hari_ini = cur.fetchall()

        # ambil semua sound
        cur.execute("SELECT id, name, file_name FROM sounds")
        sounds = cur.fetchall()

    # Cari bel berikutnya
    next_bell = None
    for jadwal_time, activity, sound_file in jadwal_hari_ini:
        if jadwal_time > now_time:
            next_bell = (jadwal_time, activity, sound_file)
            break

    return render_template("index.html", jadwal=jadwal_hari_ini, hari=hari_ini, 
                         next_bell=next_bell, sounds=sounds, 
                         categories=categories, active_category=active_category)


# ───── CEK STATUS BEL BERIKUTNYA ─────
@app.route("/api/next-bell")
@login_required
def api_next_bell():
    today_eng = datetime.datetime.now().strftime("%A")
    hari_ini = HARI_MAP.get(today_eng, today_eng)
    now_time = datetime.datetime.now().strftime("%H:%M")

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT time, activity, sound_file
            FROM schedules
            WHERE day_of_week = ?
            ORDER BY time
        """, (hari_ini,))
        jadwal_hari_ini = cur.fetchall()

    next_bell = None
    for jadwal_time, activity, sound_file in jadwal_hari_ini:
        if jadwal_time > now_time:
            next_bell = {"time": jadwal_time, "activity": activity, "sound": sound_file}
            break

    return jsonify(next_bell or {})

# ───── CORE STATUS ─────
@app.route("/api/core-status")
@login_required
def api_core_status():
    return jsonify({"status": "running" if core.is_running() else "stopped"})

# ───── TOGGLE CORE ─────
@app.route("/api/toggle-core", methods=["POST"])
@login_required
def api_toggle_core():
    if core.is_running():
        core.stop_scheduler()
        return jsonify({"status": "stopped"})
    else:
        threading.Thread(target=core.start_scheduler, daemon=True).start()
        return jsonify({"status": "running"})

# ───── PLAY MANUAL ─────
@app.route("/api/play-manual", methods=["POST"])
@login_required
def api_play_manual():
    sound_file = request.form.get("sound_file")
    if not sound_file:
        return jsonify({"success": False, "message": "File sound tidak dipilih"})

    try:
        core.stop_sound()  # hentikan kalau ada yang jalan
        core.play_sound(sound_file, activity="Manual Play")
        return jsonify({"success": True, "message": f"Memutar {sound_file}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    
# ───── STOP AUDIO ─────
@app.route("/api/stop-audio", methods=["POST"])
@login_required
def api_stop_audio():
    try:
        core.stop_sound()
        return jsonify({"success": True, "message": "Audio dihentikan"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    
# ───── UPLOAD SOUND ─────
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        file = request.files.get("sound_file")

        if not name:
            flash("Nama sound wajib diisi.", "danger")
            return redirect(url_for("upload"))

        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
            file.save(filepath)

            with _connect() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO sounds (name, file_name) VALUES (?, ?)", (name, filename))
                conn.commit()

            flash("File berhasil diupload", "success")
        else:
            flash("File belum dipilih.", "danger")

        return redirect(url_for("upload"))

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, file_name FROM sounds ORDER BY id DESC")
        sounds = cur.fetchall()

    return render_template("upload.html", sounds=sounds)

# ───── HAPUS SOUND + FILE SOUND ─────
@app.route("/delete_sound/<int:sound_id>", methods=["POST"])
@login_required
def delete_sound(sound_id):
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_name FROM sounds WHERE id = ?", (sound_id,))
        row = cur.fetchone()
        if not row:
            flash("Data sound tidak ditemukan.", "danger")
            return redirect(url_for("upload"))

        filename = row[0]
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                flash(f"Gagal menghapus file fisik: {e}", "warning")

        cur.execute("DELETE FROM sounds WHERE id = ?", (sound_id,))
        conn.commit()

    flash("Sound berhasil dihapus.", "success")
    return redirect(url_for("upload"))

# ───── LIHAT JADWAL ─────
@app.route("/schedule")
@login_required
def schedule():
    today_eng = datetime.datetime.now().strftime("%A")
    hari_ini = HARI_MAP.get(today_eng, today_eng)

    # Get categories
    categories = get_all_categories()
    active_cat = get_active_category()
    active_category = active_cat[1] if active_cat else 'normal'

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_name FROM sounds ORDER BY id DESC")
        sounds = cur.fetchall()

        # Get schedules grouped by category
        cur.execute("""
            SELECT id, day_of_week, time, activity, sound_file, category
            FROM schedules
            ORDER BY
              CASE day_of_week
                WHEN 'Senin' THEN 1
                WHEN 'Selasa' THEN 2
                WHEN 'Rabu' THEN 3
                WHEN 'Kamis' THEN 4
                WHEN 'Jumat' THEN 5
                WHEN 'Sabtu' THEN 6
                WHEN 'Minggu' THEN 7
                ELSE 8
              END, time
        """)
        schedule_list = cur.fetchall()

    return render_template("schedule.html", schedules=schedule_list, hari_ini=hari_ini, sounds=sounds, 
                         categories=categories, active_category=active_category)

# ───── EDIT JADWAL ─────
@app.route("/edit_schedule/<int:schedule_id>", methods=["GET", "POST"])
@login_required
def edit_schedule(schedule_id):
    categories = get_all_categories()
    
    with _connect() as conn:
        cur = conn.cursor()

        if request.method == "POST":
            day = request.form.get("day")
            time_val = request.form.get("time")
            activity = request.form.get("activity", "").strip()
            sound_file = request.form.get("sound_file")
            category = request.form.get("category", "normal")

            if not all([day, time_val, activity, sound_file]):
                flash("Semua field wajib diisi.", "danger")
                return redirect(url_for("edit_schedule", schedule_id=schedule_id))

            cur.execute("""
                UPDATE schedules
                SET day_of_week=?, time=?, activity=?, sound_file=?, category=?
                WHERE id=?
            """, (day, time_val, activity, sound_file, category, schedule_id))
            conn.commit()
            flash("Jadwal berhasil diperbarui.", "success")
            return redirect(url_for("schedule"))

        # kalau GET → ambil data lama
        cur.execute("SELECT id, day_of_week, time, activity, sound_file, category FROM schedules WHERE id=?", (schedule_id,))
        schedule_data = cur.fetchone()

        cur.execute("SELECT file_name FROM sounds ORDER BY id DESC")
        sounds = cur.fetchall()
    
    playlists = get_all_playlists()

    return render_template("edit_schedule.html", schedule=schedule_data, sounds=sounds, categories=categories, playlists=playlists)

# ───── TAMBAH JADWAL ─────
@app.route("/schedule/add", methods=["GET", "POST"])
@login_required
def add_schedule():
    categories = get_all_categories()
    
    if request.method == "POST":
        day = request.form.get("day")
        time_val = request.form.get("time")
        activity = request.form.get("activity", "").strip()
        sound_file = request.form.get("sound_file")
        category = request.form.get("category", "normal")

        if not all([day, time_val, activity, sound_file]):
            flash("Semua field jadwal wajib diisi.", "danger")
            return redirect(url_for("add_schedule"))

        with _connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO schedules (day_of_week, time, activity, sound_file, category)
                VALUES (?, ?, ?, ?, ?)
            """, (day, time_val, activity, sound_file, category))
            conn.commit()

        flash("Jadwal berhasil ditambahkan.", "success")
        return redirect(url_for("schedule"))

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_name FROM sounds ORDER BY id DESC")
        sounds = cur.fetchall()
    
    playlists = get_all_playlists()

    return render_template("add_schedule.html", sounds=sounds, categories=categories, playlists=playlists)

# ───── DELETE JADWAL ─────
@app.route("/delete_schedule/<int:schedule_id>", methods=["POST"])
@login_required
def delete_schedule(schedule_id):
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        conn.commit()
    flash("Jadwal berhasil dihapus.", "success")
    return redirect(url_for("schedule"))

# ───── IMPORT TEMPLATE JADWAL ─────
@app.route("/import-schedule", methods=["POST"])
@login_required
def import_schedule():
    """Import jadwal default SDIT Harapan Umat"""
    
    from config import Config
    
    # Default sound file
    default_sound = "bell.mp3"
    
    # Cek apakah sound file exists
    sound_path = os.path.join(Config.UPLOAD_FOLDER, default_sound)
    if not os.path.exists(sound_path):
        # Cari sound pertama yang ada di database
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT file_name FROM sounds LIMIT 1")
            row = cur.fetchone()
            if row:
                default_sound = row[0]
            else:
                flash("Tidak ada file sound! Upload sound dulu.", "danger")
                return redirect(url_for("schedule"))
    
    # Jadwal SELASA/RABU/KAMIS (identik)
    hari_antara = [
        ("Selasa", "07:15", "SHOLAT DHUHA DAN DZIKIR PAGI", default_sound, "normal"),
        ("Selasa", "07:30", "BTAQ", default_sound, "normal"),
        ("Selasa", "08:00", "IPAS", default_sound, "normal"),
        ("Selasa", "08:30", "IPAS", default_sound, "normal"),
        ("Selasa", "09:00", "B.INGGRIS", default_sound, "normal"),
        ("Selasa", "09:30", "B.INGGRIS", default_sound, "normal"),
        ("Selasa", "10:00", "ISTIRAHAT I", default_sound, "normal"),
        ("Selasa", "10:15", "TAHFIDZ", default_sound, "normal"),
        ("Selasa", "10:45", "TAHFIDZ", default_sound, "normal"),
        ("Selasa", "11:15", "MAKAN SIANG, SHOLAT, ISTIRAHAT II", default_sound, "normal"),
        ("Selasa", "12:25", "SCIENCE", default_sound, "normal"),
        ("Selasa", "12:55", "SCIENCE", default_sound, "normal"),
        ("Selasa", "13:25", "ISTIRAHAT III", default_sound, "normal"),
        ("Selasa", "13:40", "SDB", default_sound, "normal"),
        ("Selasa", "14:10", "SDB", default_sound, "normal"),
        ("Selasa", "15:00", "SHOLAT ASAR BERJAMA'AH DAN PULANG", default_sound, "normal"),
    ]
    
    # Jadwal lengkap
    schedules_data = [
        # SENIN
        ("Senin", "07:15", "SHOLAT DHUHA DAN DZIKIR PAGI", default_sound, "normal"),
        ("Senin", "07:30", "APEL PAGI", default_sound, "normal"),
        ("Senin", "08:00", "BTAQ", default_sound, "normal"),
        ("Senin", "08:30", "BINA KELAS", default_sound, "normal"),
        ("Senin", "09:00", "MTK", default_sound, "normal"),
        ("Senin", "09:30", "MTK", default_sound, "normal"),
        ("Senin", "10:00", "ISTIRAHAT I", default_sound, "normal"),
        ("Senin", "10:15", "B.ARAB", default_sound, "normal"),
        ("Senin", "10:45", "B.ARAB", default_sound, "normal"),
        ("Senin", "11:15", "MAKAN SIANG, SHOLAT, ISTIRAHAT II", default_sound, "normal"),
        ("Senin", "12:25", "TAHFIDZ", default_sound, "normal"),
        ("Senin", "12:55", "TAHFIDZ", default_sound, "normal"),
        ("Senin", "13:25", "PULANG", default_sound, "normal"),
    ] + hari_antara + hari_antara + hari_antara + [
        # JUM'AT
        ("Jumat", "07:15", "SHOLAT DHUHA DAN DZIKIR PAGI", default_sound, "normal"),
        ("Jumat", "07:30", "SENAM / BERKISAH", default_sound, "normal"),
        ("Jumat", "08:00", "BTAQ", default_sound, "normal"),
        ("Jumat", "08:30", "MTK", default_sound, "normal"),
        ("Jumat", "08:55", "MTK", default_sound, "normal"),
        ("Jumat", "09:20", "SKI", default_sound, "normal"),
        ("Jumat", "09:45", "AKHLAK", default_sound, "normal"),
        ("Jumat", "10:10", "ISTIRAHAT", default_sound, "normal"),
        ("Jumat", "10:25", "PJOK", default_sound, "normal"),
        ("Jumat", "10:50", "PJOK", default_sound, "normal"),
        ("Jumat", "11:15", "SHOLAT JUM'AT", default_sound, "normal"),
        ("Jumat", "12:00", "ISTIRAHAT", default_sound, "normal"),
        ("Jumat", "12:30", "PRAMUKA", default_sound, "normal"),
        ("Jumat", "13:30", "ESKTRA", default_sound, "normal"),
        ("Jumat", "14:30", "SHOLAT ASAR", default_sound, "normal"),
        ("Jumat", "15:00", "PULANG", default_sound, "normal"),
    ]
    
    # Ganti nama hari untuk RABU dan KAMIS
    schedules_data_rabu = [(day.replace("Selasa", "Rabu"), t, a, s, c) for day, t, a, s, c in hari_antara]
    schedules_data_kamis = [(day.replace("Selasa", "Kamis"), t, a, s, c) for day, t, a, s, c in hari_antara]
    
    schedules_data = schedules_data + schedules_data_rabu + schedules_data_kamis
    
    try:
        with _connect() as conn:
            cur = conn.cursor()
            
            # Cek apakah sudah ada jadwal (untuk mencegah duplikasi)
            cur.execute("SELECT COUNT(*) FROM schedules")
            existing_count = cur.fetchone()[0]
            
            if existing_count > 0:
                # Hapus jadwal lama dulu
                cur.execute("DELETE FROM schedules")
                flash(f"Menghapus {existing_count} jadwal lama...", "info")
            
            # Insert jadwal baru
            cur.executemany("""
                INSERT INTO schedules (day_of_week, time, activity, sound_file, category)
                VALUES (?, ?, ?, ?, ?)
            """, schedules_data)
            
            conn.commit()
        
        flash(f"Berhasil import {len(schedules_data)} jadwal!", "success")
    except Exception as e:
        flash(f"Gagal import jadwal: {str(e)}", "danger")
    
    return redirect(url_for("schedule"))

# ───── HISTORY (LOG) ─────
@app.route("/history", methods=["GET", "POST"])
@login_required
def history():
    if request.method == "POST":
        # tombol clear
        action = request.form.get("action")
        if action == "clear":
            clear_history()
            flash("History berhasil dikosongkan.", "success")
            return redirect(url_for("history"))

    logs = get_history(limit=300)
    return render_template("history.html", logs=logs)

# ───── SETTINGS PAGE ─────
@app.route("/settings", methods=["GET"])
@login_required
def settings():
    settings_data = get_all_settings()
    system_info = settings_manager.get_system_info()
    access_url = settings_manager.get_access_url()
    qr_exists = os.path.exists(os.path.join(Config.BASE_DIR, 'access-qr.png'))
    
    return render_template("settings.html", 
                         settings=settings_data,
                         system_info=system_info,
                         access_url=access_url,
                         qr_exists=qr_exists)

# ───── SETTINGS: GENERAL ─────
@app.route("/settings/general", methods=["POST"])
@login_required
def settings_general():
    updates = {
        'timezone': request.form.get('timezone', 'Asia/Jakarta'),
        'theme': request.form.get('theme', 'default'),
        'auto_start': 'auto_start' in request.form
    }
    
    if update_settings(updates):
        flash("Pengaturan umum berhasil disimpan.", "success")
    else:
        flash("Gagal menyimpan pengaturan.", "danger")
    
    return redirect(url_for("settings") + "#general")

# ───── SETTINGS: NETWORK ─────
@app.route("/settings/network", methods=["POST"])
@login_required
def settings_network():
    updates = {
        'port': int(request.form.get('port', 5000)),
        'static_ip_enabled': 'static_ip_enabled' in request.form,
        'static_ip': request.form.get('static_ip', ''),
        'static_gateway': request.form.get('static_gateway', ''),
        'static_dns': request.form.get('static_dns', '8.8.8.8')
    }
    
    if update_settings(updates):
        flash("Pengaturan jaringan disimpan. Restart aplikasi untuk apply port baru.", "success")
    else:
        flash("Gagal menyimpan pengaturan jaringan.", "danger")
    
    return redirect(url_for("settings") + "#network")

# ───── SETTINGS: AUDIO ─────
@app.route("/settings/audio", methods=["POST"])
@login_required
def settings_audio():
    updates = {
        'audio_output': request.form.get('audio_output', 'auto'),
        'volume': int(request.form.get('volume', 80))
    }
    
    if update_settings(updates):
        # Apply audio settings
        settings_manager.apply_audio_settings()
        flash("Pengaturan audio berhasil disimpan dan diterapkan.", "success")
    else:
        flash("Gagal menyimpan pengaturan audio.", "danger")
    
    return redirect(url_for("settings") + "#audio")

# ───── SETTINGS: GENERATE QR ─────
@app.route("/settings/generate-qr", methods=["POST"])
@login_required
def settings_generate_qr():
    success, result = settings_manager.generate_qr_code()
    
    if success:
        # Copy ke static folder untuk diakses dari web
        import shutil
        src = os.path.join(Config.BASE_DIR, 'access-qr.png')
        dst = os.path.join(Config.BASE_DIR, 'static', 'access-qr.png')
        if os.path.exists(src):
            shutil.copy(src, dst)
            flash("QR Code berhasil digenerate.", "success")
        else:
            flash("QR Code file tidak ditemukan.", "warning")
    else:
        flash(f"Gagal generate QR Code: {result}", "danger")
    
    return redirect(url_for("settings") + "#access")

# ───── SETTINGS: PASSWORD ─────
@app.route("/settings/password", methods=["POST"])
@login_required
def settings_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Verify current password
    from database import _connect
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username = ?", (current_user.username,))
        row = cur.fetchone()
        
        if not row or not check_password_hash(row[0], current_password):
            flash("Password saat ini salah.", "danger")
            return redirect(url_for("settings") + "#security")
    
    if new_password != confirm_password:
        flash("Password baru dan konfirmasi tidak cocok.", "danger")
        return redirect(url_for("settings") + "#security")
    
    if len(new_password) < 6:
        flash("Password minimal 6 karakter.", "danger")
        return redirect(url_for("settings") + "#security")
    
    # Update password
    new_hash = generate_password_hash(new_password)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
                   (new_hash, current_user.username))
        conn.commit()
    
    flash("Password berhasil diubah.", "success")
    return redirect(url_for("settings") + "#security")

# ───── SETTINGS: RESTART SERVICE ─────
@app.route("/settings/restart-service", methods=["POST"])
@login_required
def settings_restart_service():
    import subprocess
    try:
        # Restart systemd service
        subprocess.run(['sudo', 'systemctl', 'restart', 'bel-sekolah.service'], 
                      check=True, capture_output=True, text=True)
        flash("Service berhasil direstart. Halaman akan refresh dalam 5 detik.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Gagal restart service: {e.stderr}", "danger")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    
    return redirect(url_for("settings") + "#system")

# ───── API: TEST AUDIO ─────
@app.route("/api/test-audio", methods=["POST"])
@login_required
def api_test_audio():
    try:
        import subprocess
        # Create a simple beep or use existing sound
        sound_file = os.path.join(Config.UPLOAD_FOLDER, 'bell.mp3')
        if not os.path.exists(sound_file):
            # Try wav if mp3 not found
            sound_file = os.path.join(Config.UPLOAD_FOLDER, 'bell.wav')
        
        if os.path.exists(sound_file):
            ext = os.path.splitext(sound_file)[1].lower()
            if ext == '.wav':
                cmd = ['aplay', sound_file]
            else:
                cmd = ['mpg123', '-q', sound_file]
            
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return jsonify({"success": True, "message": "Audio test playing"})
        else:
            return jsonify({"success": False, "message": "No sound file available for test"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ==================== CATEGORY API ====================

@app.route("/api/categories", methods=["GET"])
@login_required
def api_get_categories():
    """Get all categories"""
    categories = get_all_categories()
    result = []
    for cat in categories:
        result.append({
            'id': cat[0],
            'name': cat[1],
            'description': cat[2] or '',
            'color': cat[3],
            'is_active': cat[4]
        })
    return jsonify(result)

@app.route("/api/active-category", methods=["GET"])
@login_required
def api_get_active_category():
    """Get active category"""
    cat = get_active_category()
    if cat:
        return jsonify({
            'id': cat[0],
            'name': cat[1],
            'description': cat[2] or '',
            'color': cat[3]
        })
    return jsonify({'name': 'normal', 'color': '#28a745'})

@app.route("/api/set-active-category", methods=["POST"])
@login_required
def api_set_active_category():
    """Set active category"""
    data = request.get_json()
    category_name = data.get('category', 'normal')
    
    # Update database
    success = set_active_category(category_name)
    if not success:
        return jsonify({'success': False, 'message': 'Kategori tidak ditemukan'})
    
    # Update settings
    update_settings({'active_category': category_name})
    
    # Restart scheduler to apply new category
    core.stop_scheduler()
    threading.Thread(target=core.start_scheduler, daemon=True).start()
    
    return jsonify({'success': True, 'message': f'Kategori changed to {category_name}'})

@app.route("/api/add-category", methods=["POST"])
@login_required
def api_add_category():
    """Add new category"""
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '')
    color = data.get('color', '#28a745')
    
    if not name:
        return jsonify({'success': False, 'message': 'Nama kategori wajib diisi'})
    
    success, message = add_category(name, description, color)
    return jsonify({'success': success, 'message': message})

@app.route("/api/delete-category/<int:category_id>", methods=["POST"])
@login_required
def api_delete_category(category_id):
    """Delete category"""
    success, message = delete_category(category_id)
    return jsonify({'success': success, 'message': message})

# ==================== PLAYLIST API ====================

@app.route("/playlists")
@login_required
def playlists_page():
    """Playlist management page"""
    playlists = get_all_playlists()
    return render_template("playlists.html", playlists=playlists)

@app.route("/api/playlists", methods=["GET"])
@login_required
def api_get_playlists():
    """Get all playlists"""
    playlists = get_all_playlists()
    return jsonify([{
        'id': p[0],
        'name': p[1],
        'description': p[2],
        'is_active': p[3],
        'item_count': p[5]
    } for p in playlists])

@app.route("/api/playlists", methods=["POST"])
@login_required
def api_create_playlist():
    """Create new playlist"""
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '')
    
    if not name:
        return jsonify({'success': False, 'message': 'Nama playlist wajib diisi'})
    
    success, playlist_id, message = add_playlist(name, description)
    return jsonify({'success': success, 'message': message, 'id': playlist_id})

@app.route("/api/playlists/<int:playlist_id>", methods=["PUT"])
@login_required
def api_update_playlist(playlist_id):
    """Update playlist"""
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '')
    
    if not name:
        return jsonify({'success': False, 'message': 'Nama playlist wajib diisi'})
    
    success, message = update_playlist(playlist_id, name, description)
    return jsonify({'success': success, 'message': message})

@app.route("/api/playlists/<int:playlist_id>", methods=["DELETE"])
@login_required
def api_delete_playlist(playlist_id):
    """Delete playlist"""
    success, message = delete_playlist(playlist_id)
    return jsonify({'success': success, 'message': message})

@app.route("/api/playlists/<int:playlist_id>/items", methods=["GET"])
@login_required
def api_get_playlist_items(playlist_id):
    """Get playlist items"""
    items = get_playlist_items(playlist_id)
    return jsonify([{
        'id': item[0],
        'position': item[1],
        'sound_id': item[2],
        'name': item[3],
        'file_name': item[4]
    } for item in items])

@app.route("/api/playlists/<int:playlist_id>/items", methods=["POST"])
@login_required
def api_add_playlist_item(playlist_id):
    """Add item to playlist"""
    data = request.get_json()
    sound_id = data.get('sound_id')
    position = data.get('position')
    
    if not sound_id:
        return jsonify({'success': False, 'message': 'Sound ID wajib diisi'})
    
    success, item_id = add_playlist_item(playlist_id, sound_id, position)
    return jsonify({'success': success, 'item_id': item_id})

@app.route("/api/playlists/items/<int:item_id>", methods=["DELETE"])
@login_required
def api_delete_playlist_item(item_id):
    """Remove item from playlist"""
    success = remove_playlist_item(item_id)
    return jsonify({'success': success})

@app.route("/api/playlists/<int:playlist_id>/reorder", methods=["POST"])
@login_required
def api_reorder_playlist(playlist_id):
    """Reorder playlist items"""
    data = request.get_json()
    positions = data.get('positions', [])  # [(item_id, new_position), ...]
    
    success = reorder_playlist_items(playlist_id, positions)
    return jsonify({'success': success})

@app.route("/api/sounds", methods=["GET"])
@login_required
def api_get_sounds():
    """Get all sounds for dropdown"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, file_name FROM sounds ORDER BY name")
        sounds = cur.fetchall()
    
    return jsonify([{
        'id': s[0],
        'name': s[1],
        'file_name': s[2]
    } for s in sounds])

def start_app():
    # init db jika dipanggil dari run.py pertama kali
    init_db()
