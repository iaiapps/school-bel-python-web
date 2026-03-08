import os
import json
import sqlite3
import socket
from config import Config
from database import get_app_setting, set_app_setting, get_all_app_settings, update_app_settings

# Default settings (fallback jika database belum ada)
DEFAULT_SETTINGS = {
    'app_name': 'Bel Sekolah',
    'port': 5000,
    'audio_output': 'auto',  # auto, hdmi, headphone
    'volume': 80,
    'timezone': 'Asia/Jakarta',
    'auto_start': True,
    'theme': 'default',
    'active_category': 'normal',
    'notification_enabled': False,
    'notification_email': '',
    'static_ip_enabled': False,
    'static_ip': '',
    'static_gateway': '',
    'static_dns': '8.8.8.8',
}

class SettingsManager:
    """Manajemen pengaturan aplikasi dengan database"""
    
    def __init__(self):
        self.settings = self.load_settings()
    
    def load_settings(self):
        """Load settings dari database"""
        try:
            db_settings = get_all_app_settings()
            # Merge dengan default untuk key yang belum ada
            settings = DEFAULT_SETTINGS.copy()
            for key, value in db_settings.items():
                # Convert value types
                if key in ['port', 'volume']:
                    settings[key] = int(value) if value else DEFAULT_SETTINGS[key]
                elif key in ['auto_start', 'static_ip_enabled', 'notification_enabled']:
                    settings[key] = value == '1' or value == 1
                else:
                    settings[key] = value if value else DEFAULT_SETTINGS[key]
            return settings
        except Exception as e:
            print(f"[SETTINGS] Error loading settings: {e}")
            return DEFAULT_SETTINGS.copy()
    
    def get(self, key, default=None):
        """Get setting value"""
        try:
            value = get_app_setting(key)
            if value is None:
                return DEFAULT_SETTINGS.get(key, default)
            # Convert type
            if key in ['port', 'volume']:
                return int(value)
            elif key in ['auto_start', 'static_ip_enabled', 'notification_enabled']:
                return value == '1' or value == 1
            return value
        except:
            return DEFAULT_SETTINGS.get(key, default)
    
    def set(self, key, value):
        """Set setting value"""
        try:
            set_app_setting(key, str(value))
            self.settings[key] = value
            return True
        except Exception as e:
            print(f"[SETTINGS] Error setting {key}: {e}")
            return False
    
    def update(self, updates):
        """Update multiple settings"""
        try:
            update_app_settings(updates)
            self.settings.update(updates)
            return True
        except Exception as e:
            print(f"[SETTINGS] Error updating settings: {e}")
            return False
    
    def get_all(self):
        """Get all settings"""
        return self.settings.copy()
    
    def get_access_url(self):
        """Generate access URL berdasarkan hostname Raspberry Pi (tidak mengubah)"""
        hostname = socket.gethostname()  # Gunakan hostname asli Raspberry Pi
        port = self.get('port', 5000)
        return f"http://{hostname}.local:{port}"
    
    def apply_audio_settings(self):
        """Apply audio settings"""
        results = []
        
        audio_output = self.get('audio_output', 'auto')
        volume = self.get('volume', 80)
        
        try:
            # Set audio output (khusus Raspberry Pi)
            if os.path.exists('/proc/device-tree/model') and 'Raspberry Pi' in open('/proc/device-tree/model').read():
                if audio_output == 'hdmi':
                    os.system("amixer cset numid=3 2 > /dev/null 2>&1")
                elif audio_output == 'headphone':
                    os.system("amixer cset numid=3 1 > /dev/null 2>&1")
                else:  # auto
                    os.system("amixer cset numid=3 0 > /dev/null 2>&1")
            
            # Set volume
            os.system(f"amixer set 'PCM' {volume}% > /dev/null 2>&1")
            results.append(('audio', True, f"Audio output: {audio_output}, Volume: {volume}%"))
        except Exception as e:
            results.append(('audio', False, str(e)))
        
        return results
    
    def generate_qr_code(self, output_file='access-qr.png'):
        """Generate QR code untuk akses URL"""
        try:
            url = self.get_access_url()
            import subprocess
            result = subprocess.run(
                ['qrencode', '-o', output_file, '-s', '10', '-l', 'H', url],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, output_file
            else:
                return False, result.stderr
        except Exception as e:
            return False, str(e)
    
    def get_system_info(self):
        """Get system information"""
        import socket
        import subprocess
        
        info = {
            'hostname': socket.gethostname(),
            'ip_address': '',
            'mac_address': '',
            'is_raspberry_pi': False,
            'cpu_temp': None,
            'app_name': self.get('app_name', 'Bel Sekolah'),
        }
        
        # Get IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            info['ip_address'] = s.getsockname()[0]
            s.close()
        except:
            pass
        
        # Check if Raspberry Pi
        if os.path.exists('/proc/device-tree/model'):
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                info['is_raspberry_pi'] = 'Raspberry Pi' in model
        
        # Get CPU temp (Raspberry Pi)
        if info['is_raspberry_pi'] and os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read().strip()) / 1000
                info['cpu_temp'] = f"{temp:.1f}°C"
        
        return info

# Global instance
settings_manager = SettingsManager()

# Helper functions untuk mudah dipakai
def get_setting(key, default=None):
    return settings_manager.get(key, default)

def set_setting(key, value):
    return settings_manager.set(key, value)

def get_all_settings():
    return settings_manager.get_all()

def update_settings(updates):
    return settings_manager.update(updates)
