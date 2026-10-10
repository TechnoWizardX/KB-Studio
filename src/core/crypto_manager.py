from cryptography.fernet import Fernet
import base64
import hashlib
from src.core.signals import signals

def get_machine_key() -> bytes:
    try:
        with open("/etc/machine-id", "r") as f:
            machine_id = f.read().strip()
    except FileNotFoundError:
        import socket
        machine_id = socket.gethostname()
    except Exception as e:
        signals.error_occured.emit(str(e))
    hasher = hashlib.sha256(machine_id.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(hasher)

def encrypt(string : str) -> str:
    """Encrypting string with machine-id"""
    try:
        if not string:
            return ""
        key = get_machine_key()
        fernet = Fernet(key)
        encrypted_bytes = fernet.encrypt(string.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")
    except Exception as e:
        signals.error_occured.emit(str(e))
        
def decrypt(string : str) -> str:
    """Decrypting string with machine-id"""
    if not string:
        return ""
    try:
        key = get_machine_key()
        fernet = Fernet(key)
        decrypted_bytes = fernet.decrypt(string.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        signals.error_occured.emit(str(e))
        return