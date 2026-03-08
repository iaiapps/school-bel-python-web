import threading
import sys
from database import init_db
from config import Config
import web
import core

def start_core():
    print("[RUN] Menjalankan pemutar bel otomatis...")
    core.start_scheduler()

if __name__ == "__main__":
    print("=" * 60)
    print("🔔 APLIKASI BEL SEKOLAH - SDIT HARAPAN UMAT JEMBER")
    print("=" * 60)
    
    # Inisialisasi database
    print("[RUN] Inisialisasi database...")
    init_db()
    
    # Jalankan core scheduler di thread terpisah
    t1 = threading.Thread(target=start_core, daemon=True)
    t1.start()
    print("[RUN] ✓ Core scheduler started")
    
    # Jalankan web server dengan Flask development server
    print(f"[RUN] Starting web server...")
    print(f"[RUN] Host: {Config.HOST}")
    print(f"[RUN] Port: {Config.PORT}")
    print(f"[RUN] Debug: {Config.DEBUG}")
    print("=" * 60)
    print(f"📡 Akses aplikasi di: http://{Config.HOST}:{Config.PORT}")
    print(f"🔐 Login: {Config.DEFAULT_ADMIN_USERNAME} / {Config.DEFAULT_ADMIN_PASSWORD}")
    print("=" * 60)
    
    try:
        # Initialize web app
        web.start_app()
        # Serve dengan Flask development server
        web.app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[RUN] Aplikasi dihentikan oleh user")
        core.stop_scheduler()
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Gagal menjalankan server: {e}")
        sys.exit(1)
