import datetime
import sqlite3
import time
import subprocess
import os
import threading
from config import Config
from database import get_playlist_sound_files, get_playlist_items, get_all_playlists, init_schedule_status_for_today, update_schedule_status, mark_missed_schedules, cleanup_old_status
from settings import get_setting

DB_PATH = Config.DB_PATH
SOUNDS_PATH = Config.UPLOAD_FOLDER

last_active_category = None

# Flag untuk inisialisasi schedule_status (sekali per hari)
_schedule_status_initialized_date = None
_last_mark_missed_minute = None

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
_last_played_lock = threading.Lock()  # Lock untuk last_played

current_playing = None  # simpan file yang sedang diputar

scheduler_running = False  # status scheduler
_scheduler_lock = threading.Lock()  # Lock untuk scheduler state
_boot_catchup_done = False  # flag: catch-up sudah jalan saat boot ini

# Audio subprocess handler
_current_audio_process = None
_audio_lock = threading.Lock()  # Lock untuk race condition

# Lock untuk playlist execution - gunakan RLock untuk reentrant
_playlist_lock = threading.RLock()

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

def _play_audio(file_path, name=None):
    """Play audio file using subprocess (non-blocking) - thread safe.
    If name is provided, sets current_playing atomically under the same lock."""
    global _current_audio_process, current_playing
    
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
            
            if name is not None:
                current_playing = name
            
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
    global _current_audio_process, _is_paused
    
    if _current_audio_process is not None:
        if _current_audio_process.poll() is None:
            try:
                _current_audio_process.terminate()
                _current_audio_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _current_audio_process.kill()
                _current_audio_process.wait()
            except Exception as e:
                print(f"[AUDIO] Error stopping audio: {e}")
        # Always clean up — even for dead processes
        _current_audio_process = None
        _is_paused = False

def _is_audio_playing():
    """Check if audio is currently playing - thread safe"""
    with _audio_lock:
        return _current_audio_process and _current_audio_process.poll() is None

_is_paused = False  # status pause audio

def pause_sound():
    """Pause audio yang sedang diputar (SIGSTOP) - thread safe"""
    global _is_paused
    with _audio_lock:
        if _current_audio_process and _current_audio_process.poll() is None:
            try:
                _current_audio_process.send_signal(19)  # SIGSTOP
                _is_paused = True
                print("[CORE] Audio dijeda (pause)")
                return True
            except Exception as e:
                print(f"[CORE] Gagal pause audio: {e}")
                return False
    return False

def resume_sound():
    """Resume audio yang di-pause (SIGCONT) - thread safe"""
    global _is_paused
    with _audio_lock:
        if _current_audio_process and _current_audio_process.poll() is None and _is_paused:
            try:
                _current_audio_process.send_signal(18)  # SIGCONT
                _is_paused = False
                print("[CORE] Audio dilanjutkan (resume)")
                return True
            except Exception as e:
                print(f"[CORE] Gagal resume audio: {e}")
                return False
    return False

def is_paused():
    """Cek apakah audio sedang di-pause"""
    with _audio_lock:
        return _is_paused

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
            if _time_matches(jadwal_time, hhmm):
                key = f"{current_day}-{jadwal_time}-{sound_file}-{active_category}"
                
                # Use lock for thread-safe access to last_played
                with _last_played_lock:
                    is_new = key not in last_played
                    if is_new:
                        last_played.add(key)
                
                if is_new:
                    # Stop current audio first - use lock for thread safety
                    with _audio_lock:
                        is_playing = _current_audio_process is not None and _current_audio_process.poll() is None
                    
                    if is_playing:
                        with _audio_lock:
                            current_name = current_playing
                        print(f"[CORE] Stop audio untuk jadwal baru: {current_name}")
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
        except Exception as e:
            print(f"[CORE] Gagal memutar playlist {sound_file}: {e}")
    else:
        print(f"[CORE] Jadwal baru: {sound_file} | {activity}")
        play_sound(sound_file, activity)

def _play_playlist(playlist_id, activity="Playlist", day_of_week=None, jadwal_time=None, category=None):
    """Play all files in a playlist sequentially with schedule checking"""
    global new_schedule_detected, _is_playing_playlist
    
    # Use lock to prevent race condition with other play requests
    if not _playlist_lock.acquire(blocking=False):
        print("[CORE] Playlist sedang berjalan, skip request baru")
        return
    
    schedule_info = None  # Initialize outside loop to persist after break
    
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
            
            # Check scheduler_running with lock for thread safety
            with _scheduler_lock:
                is_running = scheduler_running
            
            if not is_running:
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
                    # Check scheduler_running with lock for thread safety
                    with _scheduler_lock:
                        is_running = scheduler_running
                    
                    if not is_running:
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
        
        if new_schedule_detected and schedule_info:
            print("[CORE] Memutar jadwal baru setelah playlist...")
            _play_schedule_from_dict(schedule_info)
        else:
            print(f"[CORE] Playlist selesai")
            # Update status ke 'played' jika dari scheduler
            if day_of_week and jadwal_time and category:
                try:
                    played_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    update_schedule_status(day_of_week, jadwal_time, category, 'played', played_at)
                    # Log history setelah playlist benar-benar selesai
                    log_history(day_of_week, jadwal_time, activity, f"playlist:{playlist_id}")
                except Exception as e:
                    print(f"[CORE] Update status played error: {e}")
    finally:
        _playlist_lock.release()

# play sound
def play_sound(file_name, activity="Manual Play", day_of_week=None, jadwal_time=None, category=None):
    """Mulai memutar file sound (non-blocking)."""
    file_path = os.path.join(SOUNDS_PATH, file_name)
    
    if not os.path.exists(file_path):
        print(f"[CORE] File tidak ditemukan: {file_path}")
        return
    
    try:
        if _play_audio(file_path, name=file_name):
            print(f"[CORE] Memutar: {file_name}")
            
            # Update status ke 'played' jika dari scheduler
            if day_of_week and jadwal_time and category:
                try:
                    played_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    update_schedule_status(day_of_week, jadwal_time, category, 'played', played_at)
                except Exception as e:
                    print(f"[CORE] Update status played error: {e}")
            
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
    with _audio_lock:
        _stop_audio_locked()
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

def _time_matches(schedule_time, now_hhmm):
    """Cocokkan waktu jadwal dengan waktu sekarang (exact match).
    
    Handle midnight wraparound: 23:59 vs 00:00 tetap dianggap cocok.
    """
    try:
        sh, sm = map(int, schedule_time.split(":"))
        nh, nm = map(int, now_hhmm.split(":"))
        s_minutes = sh * 60 + sm
        n_minutes = nh * 60 + nm
        diff = abs(s_minutes - n_minutes)
        if diff > 720:  # lebih dari 12 jam, wraparound midnight
            diff = 1440 - diff
        return diff == 0
    except (ValueError, AttributeError):
        return schedule_time == now_hhmm

def _play_first_missed_schedule(current_day, active_category):
    """Saat boot, putar jadwal pertama (murottal) jika masih dalam window.
    
    Window: antara jadwal pertama dan jadwal kedua.
    Contoh:
      Jadwal 1: 06:00 Murottal
      Jadwal 2: 07:00 Bel Masuk
      Boot 06:30 → masih antara 06:00-07:00 → PUTAR murottal
      Boot 07:05 → sudah lewat 07:00 → SKIP (sekolah sudah mulai)
    """
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT time, activity, sound_file
                FROM schedules
                WHERE day_of_week = ? AND category = ?
                ORDER BY time ASC
            """, (current_day, active_category))
            rows = cur.fetchall()

        if not rows:
            print("[CORE] Boot catch-up: tidak ada jadwal hari ini, skip")
            return

        # Jadwal pertama (murottal)
        first_time, first_activity, first_sound = rows[0]
        now_time = datetime.datetime.now().strftime("%H:%M")

        # Kalau jadwal pertama belum lewat, skip (scheduler normal akan handle)
        if first_time >= now_time:
            print(f"[CORE] Boot catch-up: jadwal pertama {first_time} belum lewat, skip")
            return

        # Cek apakah masih ada jadwal kedua (sebagai batas window)
        if len(rows) >= 2:
            second_time = rows[1][0]
            # Kalau sudah lewat jadwal kedua, skip (terlalu telat)
            if now_time >= second_time:
                print(f"[CORE] Boot catch-up: sudah lewat jadwal kedua {second_time}, skip")
                return

        # Cek apakah sudah diputar (last_played kosong saat fresh boot)
        key = f"{current_day}-{first_time}-{first_sound}-{active_category}"
        with _last_played_lock:
            if key in last_played:
                print(f"[CORE] Boot catch-up: {first_time} sudah diputar, skip")
                return

        # Putar sekarang
        print(f"[CORE] Boot catch-up: memutar {first_time} {first_activity} ({first_sound})")
        
        # Update status ke 'playing'
        try:
            update_schedule_status(current_day, first_time, active_category, 'playing')
        except Exception as e:
            print(f"[CORE] Update status playing error: {e}")
        
        if first_sound.startswith("playlist:"):
            try:
                playlist_id = int(first_sound.split(":")[1])
                _play_playlist(playlist_id, f"[Boot Catch-up] {first_activity}", current_day, first_time, active_category)
                # log_history sudah dipanggil di dalam _play_playlist setelah selesai
            except (ValueError, IndexError):
                print(f"[CORE] Boot catch-up: format playlist tidak valid: {first_sound}")
        else:
            play_sound(first_sound, f"[Boot Catch-up] {first_activity}", current_day, first_time, active_category)

    except Exception as e:
        print(f"[CORE] Boot catch-up error: {e}")

def start_scheduler():
    """Start the scheduler - thread safe with double-start prevention"""
    global last_played, current_playing, scheduler_running, last_active_category, _boot_catchup_done
    
    # Use lock to prevent race condition with double start
    with _scheduler_lock:
        if scheduler_running:
            print("[CORE] Scheduler sudah berjalan, skip start")
            return
        scheduler_running = True
        last_active_category = None
        print("[CORE] Scheduler dimulai.")
    
    # Cleanup old schedule_status (>30 hari) saat boot
    try:
        cleanup_old_status(30)
    except Exception as e:
        print(f"[CORE] Cleanup status error: {e}")
    
    # Boot catch-up: putar jadwal pertama jika masih dalam window (sekali saja per boot)
    if not _boot_catchup_done:
        _boot_catchup_done = True
        try:
            active_cat = get_setting('active_category', 'normal')
        except Exception:
            active_cat = 'normal'
        now = datetime.datetime.now()
        day_eng = now.strftime("%A")
        day_id = HARI_MAP.get(day_eng, day_eng)
        threading.Thread(
            target=_play_first_missed_schedule,
            args=(day_id, active_cat),
            daemon=True
        ).start()
    
    while True:
        # Check scheduler_running with lock for thread safety
        with _scheduler_lock:
            if not scheduler_running:
                break
        now = datetime.datetime.now()
        current_day_eng = now.strftime("%A")
        current_day = HARI_MAP.get(current_day_eng, current_day_eng)  # ex: Senin
        hhmm = now.strftime("%H:%M")

        # Get active category from settings
        try:
            active_category = get_setting('active_category', 'normal')
        except Exception:
            active_category = 'normal'

        # Reset last_played jika category berubah
        if last_active_category != active_category:
            print(f"[CORE] Kategori berubah: {last_active_category} -> {active_category}")
            with _last_played_lock:
                last_played.clear()
            last_active_category = active_category
            global _schedule_status_initialized_date
            _schedule_status_initialized_date = None  # Reset when category changes
        
        # Initialize schedule_status untuk hari ini (sekali per hari)
        today = now.strftime('%Y-%m-%d')
        if _schedule_status_initialized_date != today:
            try:
                with _connect() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT time, activity, sound_file
                        FROM schedules
                        WHERE day_of_week = ? AND category = ?
                    """, (current_day, active_category))
                    schedules_today = cur.fetchall()
                
                # Insert ke schedule_status jika belum ada untuk hari ini
                if schedules_today:
                    init_schedule_status_for_today(current_day, active_category, schedules_today)
                _schedule_status_initialized_date = today
            except Exception as e:
                print(f"[CORE] Init schedule_status error: {e}")
        
        # Tandai jadwal yang sudah lewat sebagai missed (sekali per menit)
        current_minute = now.strftime('%Y-%m-%d %H:%M')
        if _last_mark_missed_minute != current_minute:
            try:
                mark_missed_schedules(current_day, active_category, hhmm)
                _last_mark_missed_minute = current_minute
            except Exception as e:
                print(f"[CORE] Mark missed error: {e}")

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
            if _time_matches(jadwal_time, hhmm):
                key = f"{current_day}-{jadwal_time}-{sound_file}-{active_category}"
                
                # Check + add ATOMIK dalam satu lock, SEBELUM diputar.
                # Ini mencegah race dengan check_and_play_new_schedule()
                # (thread playlist) yang sama-sama melihat is_new=True,
                # yang menyebabkan bel berbunyi dua kali.
                with _last_played_lock:
                    is_new = key not in last_played
                    if is_new:
                        last_played.add(key)
                
                if is_new:
                    # hentikan audio lama kalau masih main
                    if _is_audio_playing():
                        with _audio_lock:
                            current_name = current_playing
                        print(f"[CORE] Stop audio lama: {current_name}")
                        # Use lock to stop playlist properly
                        if _playlist_lock.acquire(blocking=False):
                            try:
                                stop_sound()
                            finally:
                                _playlist_lock.release()
                        else:
                            stop_sound()

                    # Update status ke 'playing'
                    try:
                        update_schedule_status(current_day, jadwal_time, active_category, 'playing')
                    except Exception as e:
                        print(f"[CORE] Update status playing error: {e}")

                    # Cek apakah sound_file adalah playlist (format: "playlist:<id>")
                    if sound_file.startswith("playlist:"):
                        try:
                            playlist_id = int(sound_file.split(":")[1])
                            print(f"[CORE] Memutar playlist ID {playlist_id} | {activity} ({current_day} {jadwal_time})")
                            # Run playlist in separate thread agar scheduler tidak blocked
                            # log_history akan dipanggil di dalam _play_playlist setelah selesai
                            threading.Thread(
                                target=_play_playlist,
                                args=(playlist_id, activity, current_day, jadwal_time, active_category),
                                daemon=True
                            ).start()
                        except (ValueError, IndexError) as e:
                            print(f"[CORE] Invalid playlist format: {sound_file}")
                    else:
                        # Single file
                        print(f"[CORE] Memutar bel: {sound_file} | {activity} ({current_day} {jadwal_time}) [Kategori: {active_category}]")
                        play_sound(sound_file, activity, current_day, jadwal_time, active_category)

        # bersihkan set sesekali
        if len(last_played) > 2000:
            # buang entri yang bukan hari & waktu sekarang agar tidak tumbuh tak terbatas
            with _last_played_lock:
                last_played.intersection_update(
                    k for k in list(last_played) if hhmm in k and current_day in k and active_category in k
                )

        time.sleep(1)  # cek tiap detik agar tepat waktu

def stop_scheduler():
    """Berhentikan scheduler - thread safe"""
    global scheduler_running
    with _scheduler_lock:
        scheduler_running = False
    stop_sound()
    print("[CORE] Scheduler dihentikan.")

def is_running():
    """Cek apakah scheduler aktif - thread safe"""
    with _scheduler_lock:
        return scheduler_running
