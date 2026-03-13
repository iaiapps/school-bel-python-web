import datetime
import sqlite3
import time
import subprocess
import os
import threading
from config import Config
from database import get_playlist_sound_files, get_playlist_items, get_all_playlists
from settings import get_setting

DB_PATH = Config.DB_PATH
SOUNDS_PATH = Config.UPLOAD_FOLDER

last_active_category = None

# Mapping hari Inggris ke Indonesia
HARI_MAP = {
    "Monday": "Senin",
    "Tuesday": "Selasa",
    "Wednesday": "Rabu",
    "Thursday": "Kamis",
    "Friday": "Jumat",
    "Saturday": "Sabtu",
    "Sunday": "Minggu"
}

# untuk mencegah memutar berkali-kali dalam selang 1 menit
last_played = set()
current_playing = None  # simpan file yang sedang diputar
scheduler_running = False  # status scheduler

# Audio subprocess handler
_current_audio_process = None
_audio_lock = threading.Lock()  # Lock untuk race condition

# Lock untuk playlist execution
_playlist_lock = threading.Lock()

# Flag untuk mencegah nested playlist play
_is_playing_playlist = False

def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    # penting untuk mengurangi lock saat paralel dengan web
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def _get_audio_command(file_path):
    """Return appropriate audio command based on file extension"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.wav':
        # WAV files use aplay (lightweight, built-in ALSA)
        return ['aplay', file_path]
    else:
        # MP3 and other formats use mpg123
        return ['mpg123', '-q', file_path]  # -q for quiet mode

def _play_audio(file_path):
    """Play audio file using subprocess (non-blocking) - thread safe"""
    global _current_audio_process
    
    with _audio_lock:
        try:
            # Stop any currently playing audio first
            _stop_audio_locked()
            
            # Get appropriate command
            cmd = _get_audio_command(file_path)
            
            # Start new audio process
            _current_audio_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            return True
        except Exception as e:
            print(f"[AUDIO] Gagal memutar {file_path}: {e}")
            return False

def _stop_audio():
    """Stop currently playing audio - thread safe"""
    with _audio_lock:
        _stop_audio_locked()

def _stop_audio_locked():
    """Stop currently playing audio - internal, no lock"""
    global _current_audio_process
    
    if _current_audio_process and _current_audio_process.poll() is None:
        try:
            _current_audio_process.terminate()
            _current_audio_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _current_audio_process.kill()
            _current_audio_process.wait()
        except Exception as e:
            print(f"[AUDIO] Error stopping audio: {e}")
        finally:
            _current_audio_process = None

def _is_audio_playing():
    """Check if audio is currently playing - thread safe"""
    with _audio_lock:
        return _current_audio_process and _current_audio_process.poll() is None

# Flag untuk menandai jadwal baru terdeteksi
new_schedule_detected = False

def check_and_play_new_schedule():
    """Check if there's a new schedule. Returns schedule info dict if new schedule found, None otherwise."""
    global last_played
    
    try:
        now = datetime.datetime.now()
        current_day_eng = now.strftime("%A")
        current_day = HARI_MAP.get(current_day_eng, current_day_eng)
        hhmm = now.strftime("%H:%M")
        
        active_category = get_setting('active_category', 'normal')
        
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT time, activity, sound_file
                FROM schedules
                WHERE day_of_week = ? AND category = ?
            """, (current_day, active_category))
            rows = cur.fetchall()
        
        for jadwal_time, activity, sound_file in rows:
            if jadwal_time == hhmm:
                key = f"{current_day}-{jadwal_time}-{sound_file}-{active_category}"
                if key not in last_played:
                    # Stop current audio first - use lock for thread safety
                    with _audio_lock:
                        is_playing = _current_audio_process is not None and _current_audio_process.poll() is None
                    
                    if is_playing:
                        print(f"[CORE] Stop audio untuk jadwal baru: {current_playing}")
                        # Try to acquire playlist lock to stop playlist
                        if _playlist_lock.acquire(blocking=False):
                            try:
                                stop_sound()
                            finally:
                                _playlist_lock.release()
                        else:
                            # Playlist is running, force stop
                            stop_sound()
                    
                    # Return schedule info for caller to play (avoid nested call)
                    last_played.add(key)
                    return {
                        'day': current_day,
                        'time': jadwal_time,
                        'activity': activity,
                        'sound_file': sound_file
                    }
    except Exception as e:
        print(f"[CORE] Error check schedule: {e}")
    
    return None

def _play_schedule_from_dict(schedule_info):
    """Play schedule from info dict returned by check_and_play_new_schedule()"""
    if not schedule_info:
        return
    
    sound_file = schedule_info['sound_file']
    activity = schedule_info['activity']
    current_day = schedule_info['day']
    jadwal_time = schedule_info['time']
    
    if sound_file.startswith("playlist:"):
        try:
            playlist_id = int(sound_file.split(":")[1])
            print(f"[CORE] Jadwal baru: Playlist ID {playlist_id} | {activity}")
            _play_playlist(playlist_id, activity)
            log_history(current_day, jadwal_time, activity, sound_file)
        except:
            pass
    else:
        print(f"[CORE] Jadwal baru: {sound_file} | {activity}")
        play_sound(sound_file, activity)

def _play_playlist(playlist_id, activity="Playlist"):
    """Play all files in a playlist sequentially with schedule checking"""
    global new_schedule_detected, _is_playing_playlist
    
    # Use lock to prevent race condition with other play requests
    if not _playlist_lock.acquire(blocking=False):
        print("[CORE] Playlist sedang berjalan, skip request baru")
        return
    
    try:
        files = get_playlist_sound_files(playlist_id)
        
        if not files:
            print(f"[CORE] Playlist {playlist_id} kosong atau tidak ditemukan")
            return
        
        print(f"[CORE] Memutar playlist dengan {len(files)} file")
        _is_playing_playlist = True
        
        for file_path in files:
            # Reset flag
            new_schedule_detected = False
            
            if not scheduler_running:
                print("[CORE] Scheduler berhenti, playlist dihentikan")
                break
            
            file_name = os.path.basename(file_path)
            
            # Start playing file
            try:
                _play_audio(file_path)
                print(f"[CORE] Memutar: {file_name}")
                
                # Wait with periodic checking for new schedule
                # Use lock for thread-safe access to _current_audio_process
                with _audio_lock:
                    process = _current_audio_process
                
                while process is not None and process.poll() is None:
                    if not scheduler_running:
                        print("[CORE] Scheduler berhenti")
                        break
                    
                    # Check for new schedule every 1 second
                    time.sleep(1)
                    
                    # Check if new schedule detected (just detect, don't play to avoid nested call)
                    schedule_info = check_and_play_new_schedule()
                    if schedule_info:
                        print("[CORE] Jadwal baru terdeteksi di tengah playlist!")
                        new_schedule_detected = True
                        # Play the new schedule AFTER breaking out of loop
                        break
                    
                    # Re-check process status with lock
                    with _audio_lock:
                        process = _current_audio_process
                
                if new_schedule_detected:
                    break
                    
                print(f"[CORE] Selesai: {file_name}")
            except Exception as e:
                print(f"[CORE] Error memutar {file_name}: {e}")
                continue
        
        _is_playing_playlist = False
        print(f"[CORE] Playlist selesai")
    finally:
        _playlist_lock.release()

# play sound
def play_sound(file_name, activity="Manual Play"):
    """Mulai memutar file sound (non-blocking)."""
    global current_playing
    
    file_path = os.path.join(SOUNDS_PATH, file_name)
    
    if not os.path.exists(file_path):
        print(f"[CORE] File tidak ditemukan: {file_path}")
        return
    
    try:
        if _play_audio(file_path):
            with _audio_lock:
                current_playing = file_name
            print(f"[CORE] Memutar: {file_name}")
            
            # Catat ke history juga, play manual
            now = datetime.datetime.now()
            current_day_eng = now.strftime("%A")
            current_day = HARI_MAP.get(current_day_eng, current_day_eng)
            jam = now.strftime("%H:%M")
            log_history(current_day, jam, activity, file_name)
    except Exception as e:
        print(f"[CORE] Gagal memutar {file_name}: {e}")

# stop sound
def stop_sound():
    """Hentikan suara saat ini."""
    global current_playing
    _stop_audio()
    with _audio_lock:
        current_playing = None
    print("[CORE] Audio dihentikan")

def log_history(day_id, jam, activity, sound_file):
    # catat ke tabel history
    played_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO history (played_at, day_of_week, time, activity, sound_file)
                VALUES (?, ?, ?, ?, ?)
            """, (played_at, day_id, jam, activity, sound_file))
            conn.commit()
    except Exception as e:
        print(f"[CORE] Gagal menulis history: {e}")

def start_scheduler():
    print("[CORE] Scheduler dimulai.")
    global last_played, current_playing, scheduler_running, last_active_category
    scheduler_running = True
    last_active_category = None

    while scheduler_running:
        now = datetime.datetime.now()
        current_day_eng = now.strftime("%A")
        current_day = HARI_MAP.get(current_day_eng, current_day_eng)  # ex: Senin
        hhmm = now.strftime("%H:%M")

        # Get active category from settings
        try:
            active_category = get_setting('active_category', 'normal')
        except:
            active_category = 'normal'

        # Reset last_played jika category berubah
        if last_active_category != active_category:
            print(f"[CORE] Kategori berubah: {last_active_category} -> {active_category}")
            last_played.clear()
            last_active_category = active_category

        try:
            with _connect() as conn:
                cur = conn.cursor()
                # ambil time, activity, sound_file (bisa single file atau playlist) untuk hari ini
                cur.execute("""
                    SELECT time, activity, sound_file
                    FROM schedules
                    WHERE day_of_week = ? AND category = ?
                """, (current_day, active_category))
                rows = cur.fetchall()
        except Exception as e:
            print(f"[CORE] DB error: {e}")
            rows = []

        for jadwal_time, activity, sound_file in rows:
            if jadwal_time == hhmm:
                key = f"{current_day}-{jadwal_time}-{sound_file}-{active_category}"
                if key not in last_played:
                    # hentikan audio lama kalau masih main
                    if _is_audio_playing():
                        print(f"[CORE] Stop audio lama: {current_playing}")
                        stop_sound()

                    # Cek apakah sound_file adalah playlist (format: "playlist:<id>")
                    if sound_file.startswith("playlist:"):
                        try:
                            playlist_id = int(sound_file.split(":")[1])
                            print(f"[CORE] Memutar playlist ID {playlist_id} | {activity} ({current_day} {jadwal_time})")
                            _play_playlist(playlist_id, activity)
                            # Log hanya untuk playlist, bukan per file
                            log_history(current_day, jadwal_time, activity, sound_file)
                        except (ValueError, IndexError) as e:
                            print(f"[CORE] Invalid playlist format: {sound_file}")
                    else:
                        # Single file
                        print(f"[CORE] Memutar bel: {sound_file} | {activity} ({current_day} {jadwal_time}) [Kategori: {active_category}]")
                        play_sound(sound_file, activity)
                    
                    last_played.add(key)

        # bersihkan set sesekali
        if len(last_played) > 2000:
            # buang entri yang bukan hari & waktu sekarang agar tidak tumbuh tak terbatas
            last_played = {k for k in last_played if hhmm in k and current_day in k and active_category in k}

        time.sleep(1)  # cek tiap detik agar tepat waktu

def stop_scheduler():
    """Berhentikan scheduler"""
    global scheduler_running
    scheduler_running = False
    stop_sound()
    print("[CORE] Scheduler dihentikan.")

def is_running():
    """Cek apakah scheduler aktif"""
    return scheduler_running
