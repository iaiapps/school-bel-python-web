import os
import sqlite3
from werkzeug.utils import secure_filename
from config import Config

SOUNDS_FOLDER = Config.UPLOAD_FOLDER

def get_all_sounds():
    """Get all sounds from database with folder info"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, file_name
            FROM sounds
            ORDER BY file_name
        """)
        return cur.fetchall()

def get_sound_by_id(sound_id):
    """Get sound by ID"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, file_name
            FROM sounds
            WHERE id = ?
        """, (sound_id,))
        return cur.fetchone()

def add_sound(name, file_name):
    """Add sound to database"""
    with _connect() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO sounds (name, file_name)
                VALUES (?, ?)
            """, (name, file_name))
            conn.commit()
            return True, cur.lastrowid
        except sqlite3.IntegrityError:
            return False, None

def delete_sound(sound_id):
    """Delete sound from database"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sounds WHERE id = ?", (sound_id,))
        conn.commit()
        return cur.rowcount > 0

def delete_sounds_bulk(sound_ids):
    """Delete multiple sounds"""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM sounds WHERE id IN ({','.join('?' * len(sound_ids))})", sound_ids)
        conn.commit()
        return cur.rowcount

def scan_sounds_folder():
    """
    Scan sounds folder recursively and return all audio files
    Returns list of relative paths
    """
    audio_files = []
    
    if not os.path.exists(SOUNDS_FOLDER):
        return audio_files
    
    for root, dirs, files in os.walk(SOUNDS_FOLDER):
        for file in files:
            if file.lower().endswith(('.mp3', '.wav')):
                # Get relative path from sounds folder
                rel_path = os.path.relpath(root, SOUNDS_FOLDER)
                if rel_path == '.':
                    # File in root
                    audio_files.append(file)
                else:
                    # File in subfolder
                    audio_files.append(os.path.join(rel_path, file))
    
    return sorted(audio_files)

def sync_sounds_with_folder(delete_missing=False):
    """
    Sync database with sounds folder
    
    Returns:
        dict: {
            'new': [list of new files added],
            'missing': [list of files removed from DB],
            'unchanged': [list of files unchanged],
            'total': total count
        }
    """
    result = {
        'new': [],
        'missing': [],
        'unchanged': [],
        'total': 0
    }
    
    # Scan folder
    folder_files = set(scan_sounds_folder())
    
    # Get DB files
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, file_name FROM sounds")
        db_files = {row[2]: (row[0], row[1]) for row in cur.fetchall()}  # {file_name: (id, name)}
    
    db_file_set = set(db_files.keys())
    
    # Find new files (in folder but not in DB)
    new_files = folder_files - db_file_set
    
    # Find missing files (in DB but not in folder)
    missing_files = db_file_set - folder_files
    
    # Find unchanged files
    unchanged_files = folder_files & db_file_set
    
    # Add new files to DB
    for file_path in new_files:
        name = os.path.splitext(os.path.basename(file_path))[0]
        add_sound(name, file_path)
        result['new'].append(file_path)
    
    # Delete missing files from DB (if enabled)
    if delete_missing:
        for file_path in missing_files:
            sound_id = db_files[file_path][0]
            delete_sound(sound_id)
            result['missing'].append(file_path)
    else:
        result['missing'] = list(missing_files)
    
    # Unchanged
    result['unchanged'] = list(unchanged_files)
    result['total'] = len(folder_files)
    
    return result

def get_folder_structure():
    """
    Get folder structure with sounds
    Returns nested dict structure
    """
    sounds = get_all_sounds()
    structure = {'root': []}
    
    for sound_id, name, file_name in sounds:
        if '/' in file_name or '\\' in file_name:
            # Has folder
            parts = file_name.split('/') if '/' in file_name else file_name.split('\\')
            folder = parts[0]
            
            if folder not in structure:
                structure[folder] = []
            
            structure[folder].append({
                'id': sound_id,
                'name': name,
                'file': parts[-1],
                'path': file_name
            })
        else:
            # Root level
            structure['root'].append({
                'id': sound_id,
                'name': name,
                'file': file_name,
                'path': file_name
            })
    
    return structure

def create_folder(folder_name):
    """Create new folder in sounds directory"""
    folder_path = os.path.join(SOUNDS_FOLDER, secure_filename(folder_name))
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return True, folder_path
    return False, None

def get_folders():
    """Get list of all folders in sounds directory"""
    folders = ['root']  # Include root as virtual folder
    
    if os.path.exists(SOUNDS_FOLDER):
        for item in os.listdir(SOUNDS_FOLDER):
            item_path = os.path.join(SOUNDS_FOLDER, item)
            if os.path.isdir(item_path):
                folders.append(item)
    
    return sorted(folders)

# Import from database module
from database import _connect
