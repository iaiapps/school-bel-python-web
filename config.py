import os
import secrets

class Config:
    # Base directory
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Secret key untuk session
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database
    DB_PATH = os.path.join(BASE_DIR, 'database.db')
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'sounds')
    
    # Server settings
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    # Default admin credentials (hash dengan werkzeug)
    DEFAULT_ADMIN_USERNAME = 'admin'
    DEFAULT_ADMIN_PASSWORD = 'admin123'  # akan di-hash saat pertama kali
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = 86400  # 24 jam
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
