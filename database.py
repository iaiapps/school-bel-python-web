import sqlite3
import os
from werkzeug.security import generate_password_hash

def _connect(db_path=None):
    if db_path is None:
        from config import Config
        db_path = Config.DB_PATH
    
    # timeout agar mengurangi "database is locked"
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")   # lebih tahan akses paralel
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")    # enable foreign key constraints
    return conn

def init_db():
    from config import Config
    
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    with _connect() as conn:
        cur = conn.cursor()

        # Tabel categories
        cur.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                color TEXT DEFAULT '#28a745',
                is_active INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default categories if empty
        cur.execute("SELECT COUNT(*) FROM categories")
        if cur.fetchone()[0] == 0:
            default_categories = [
                ('normal', 'Jadwal Normal Hari Sekolah', '#28a745', 1),
                ('ujian', 'Jadwal Ujian', '#dc3545', 0),
                ('puasa', 'Jadwal Puasa', '#17a2b8', 0),
            ]
            cur.executemany("""
                INSERT INTO categories (name, description, color, is_active) 
                VALUES (?, ?, ?, ?)
            """, default_categories)

        # Tabel sound
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                file_name TEXT NOT NULL
            )
        """)

        # Tabel schedules (dengan category)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week TEXT NOT NULL,   -- Senin, Selasa, ...
                time TEXT NOT NULL,          -- HH:MM
                activity TEXT NOT NULL,      -- Nama kegiatan
                sound_file TEXT NOT NULL,    -- nama file di folder sounds
                category TEXT DEFAULT 'normal',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index untuk pencarian cepat
        cur.execute("CREATE INDEX IF NOT EXISTS idx_schedules_dow_time ON schedules(day_of_week, time)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_schedules_category ON schedules(category)")

        # Tabel playlists untuk murottal dan audio sequence
        cur.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabel playlist_items untuk urutan file dalam playlist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS playlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                sound_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (sound_id) REFERENCES sounds(id) ON DELETE CASCADE
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist ON playlist_items(playlist_id, position)")

        # Tabel history (log)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                played_at TEXT NOT NULL,     -- timestamp ISO (YYYY-MM-DD HH:MM:SS)
                day_of_week TEXT NOT NULL,   -- hari (Indonesia)
                time TEXT NOT NULL,          -- HH:MM (jadwal)
                activity TEXT NOT NULL,
                sound_file TEXT NOT NULL
            )
        """)

        # Tabel users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabel app_settings untuk pengaturan aplikasi
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default settings jika belum ada
        default_settings = [
            ('app_name', 'Bel Sekolah'),
            ('port', '5000'),
            ('audio_output', 'auto'),
            ('volume', '80'),
            ('timezone', 'Asia/Jakarta'),
            ('auto_start', '1'),
            ('theme', 'default'),
            ('active_category', 'normal'),
            ('static_ip_enabled', '0'),
            ('static_ip', ''),
            ('static_gateway', ''),
            ('static_dns', '8.8.8.8'),
        ]
        
        for key, value in default_settings:
            cur.execute("""
                INSERT OR IGNORE INTO app_settings (key, value)
                VALUES (?, ?)
            """, (key, value))

        conn.commit()
    
    print("[DB] Database dasar siap digunakan.")
    
    # Create default admin user if not exists
    create_default_admin()

# Helper untuk ambil data (opsional dipakai web.py)
def get_history(limit=200):
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, played_at, day_of_week, time, activity, sound_file
            FROM history
            ORDER BY played_at DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()

def clear_history():
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM history")
        conn.commit()

# User management functions
def create_default_admin():
    """Create default admin user if not exists"""
    from config import Config
    
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (Config.DEFAULT_ADMIN_USERNAME,))
        if not cur.fetchone():
            password_hash = generate_password_hash(Config.DEFAULT_ADMIN_PASSWORD)
            cur.execute("""
                INSERT INTO users (username, password_hash, is_active)
                VALUES (?, ?, 1)
            """, (Config.DEFAULT_ADMIN_USERNAME, password_hash))
            conn.commit()
            print(f"[DB] Default admin user created: {Config.DEFAULT_ADMIN_USERNAME}")
        else:
            print("[DB] Admin user already exists")

def get_user_by_username(username):
    """Get user by username"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, password_hash, is_active
            FROM users
            WHERE username = ?
        """, (username,))
        return cur.fetchone()

def get_user_by_id(user_id):
    """Get user by ID"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, password_hash, is_active
            FROM users
            WHERE id = ?
        """, (user_id,))
        return cur.fetchone()

# ==================== CATEGORY FUNCTIONS ====================

def get_all_categories():
    """Get all categories"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, description, color, is_active, created_at
            FROM categories
            ORDER BY id
        """)
        return cur.fetchall()

def get_active_category():
    """Get active category"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, description, color
            FROM categories
            WHERE is_active = 1
            LIMIT 1
        """)
        return cur.fetchone()

def set_active_category(category_name):
    """Set active category"""
    with _connect() as conn:
        cur = conn.cursor()
        # Check if category exists
        cur.execute("SELECT COUNT(*) FROM categories WHERE name = ?", (category_name,))
        if cur.fetchone()[0] == 0:
            return False
        
        # First, deactivate all
        cur.execute("UPDATE categories SET is_active = 0")
        # Then activate the selected one
        cur.execute("UPDATE categories SET is_active = 1 WHERE name = ?", (category_name,))
        conn.commit()
    return True

def add_category(name, description='', color='#28a745'):
    """Add new category"""
    with _connect() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO categories (name, description, color, is_active)
                VALUES (?, ?, ?, 0)
            """, (name, description, color))
            conn.commit()
            return True, "Kategori berhasil ditambahkan"
        except sqlite3.IntegrityError:
            return False, "Nama kategori sudah ada"

def delete_category(category_id):
    """Delete category"""
    with _connect() as conn:
        cur = conn.cursor()
        # Check if category has schedules
        cur.execute("SELECT COUNT(*) FROM schedules WHERE category = (SELECT name FROM categories WHERE id = ?)", (category_id,))
        count = cur.fetchone()[0]
        if count > 0:
            return False, "Kategori masih digunakan di jadwal"
        
        cur.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        return True, "Kategori berhasil dihapus"

def get_schedules_by_category(category):
    """Get all schedules for a specific category"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, day_of_week, time, activity, sound_file, category, created_at
            FROM schedules
            WHERE category = ?
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
        """, (category,))
        return cur.fetchall()

# ==================== PLAYLIST FUNCTIONS ====================

def get_all_playlists():
    """Get all playlists with item count"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.name, p.description, p.is_active, p.created_at,
                   COUNT(pi.id) as item_count
            FROM playlists p
            LEFT JOIN playlist_items pi ON p.id = pi.playlist_id
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """)
        return cur.fetchall()

def get_playlist(playlist_id):
    """Get playlist by ID"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, description, is_active, created_at
            FROM playlists
            WHERE id = ?
        """, (playlist_id,))
        return cur.fetchone()

def get_playlist_items(playlist_id):
    """Get all items in a playlist with sound details"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT pi.id, pi.position, s.id as sound_id, s.name, s.file_name
            FROM playlist_items pi
            JOIN sounds s ON pi.sound_id = s.id
            WHERE pi.playlist_id = ?
            ORDER BY pi.position
        """, (playlist_id,))
        return cur.fetchall()

def get_playlist_sound_files(playlist_id):
    """Get list of sound file paths for a playlist"""
    from config import Config
    items = get_playlist_items(playlist_id)
    files = []
    for item in items:
        # item = (id, position, sound_id, name, file_name)
        file_path = os.path.join(Config.UPLOAD_FOLDER, item[4])
        if os.path.exists(file_path):
            files.append(file_path)
    return files

def add_playlist(name, description=''):
    """Add new playlist"""
    with _connect() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO playlists (name, description, is_active)
                VALUES (?, ?, 1)
            """, (name, description))
            conn.commit()
            return True, cur.lastrowid, "Playlist berhasil ditambahkan"
        except sqlite3.IntegrityError:
            return False, None, "Nama playlist sudah ada"

def update_playlist(playlist_id, name, description):
    """Update playlist"""
    with _connect() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE playlists
                SET name = ?, description = ?
                WHERE id = ?
            """, (name, description, playlist_id))
            conn.commit()
            return True, "Playlist berhasil diupdate"
        except sqlite3.IntegrityError:
            return False, "Nama playlist sudah ada"

def delete_playlist(playlist_id):
    """Delete playlist (cascade akan hapus items juga)"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.commit()
        return True, "Playlist berhasil dihapus"

def add_playlist_item(playlist_id, sound_id, position=None):
    """Add item to playlist"""
    with _connect() as conn:
        cur = conn.cursor()
        
        # If position not specified, add at the end
        if position is None:
            cur.execute("""
                SELECT MAX(position) FROM playlist_items WHERE playlist_id = ?
            """, (playlist_id,))
            max_pos = cur.fetchone()[0]
            position = (max_pos or 0) + 1
        
        cur.execute("""
            INSERT INTO playlist_items (playlist_id, sound_id, position)
            VALUES (?, ?, ?)
        """, (playlist_id, sound_id, position))
        conn.commit()
        return True, cur.lastrowid

def remove_playlist_item(item_id):
    """Remove item from playlist"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM playlist_items WHERE id = ?", (item_id,))
        conn.commit()
        return True

def reorder_playlist_items(playlist_id, item_positions):
    """Reorder items in playlist
    item_positions: list of (item_id, new_position)
    """
    with _connect() as conn:
        cur = conn.cursor()
        for item_id, position in item_positions:
            cur.execute("""
                UPDATE playlist_items SET position = ? WHERE id = ?
            """, (position, item_id))
        conn.commit()
        return True

# ==================== APP SETTINGS FUNCTIONS ====================

def get_app_setting(key, default=None):
    """Get app setting value"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

def set_app_setting(key, value):
    """Set app setting value"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
        """, (key, value))
        conn.commit()
        return True

def get_all_app_settings():
    """Get all app settings as dict"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM app_settings")
        rows = cur.fetchall()
        return {row[0]: row[1] for row in rows}

def update_app_settings(updates):
    """Update multiple settings"""
    for key, value in updates.items():
        set_app_setting(key, str(value))
    return True
