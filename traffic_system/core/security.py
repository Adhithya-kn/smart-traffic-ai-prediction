"""
traffic_system/core/security.py - Authentication, Password Hashing & Role-Based Access Control
"""

import os
import json
import hashlib
import secrets
import time
import tempfile
import threading
from typing import Optional, Dict, Any
from pathlib import Path
from traffic_system.config import USERS_DB_PATH
from traffic_system.core.entities import UserRole

# Standard PBKDF2 iteration count: balanced for sub-millisecond local auth and brute-force resistance
ITERATIONS = 20_000

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hashes a password with PBKDF2-HMAC-SHA256 and a 16-byte random salt.
    Standard Python stdlib cryptographic primitive; zero external C-dependencies or memory bloat.
    """
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        ITERATIONS
    )
    return dk.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Constant-time verification of candidate password."""
    candidate_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate_hash, password_hash)

def atomic_json_dump(data: Any, target_path: Path):
    """POSIX Two-Phase Atomic Write: fsync to tempfile and atomic rename."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=target_path.parent, prefix="atomic_", suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

SESSION_TTL_SECONDS = 86400  # 24-hour bearer token TTL

class SecurityManager:
    """Manages user registration, login, and active token sessions."""
    def __init__(self, db_path: Path = USERS_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.users: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._load_users()

    def _load_users(self):
        with self._lock:
            if self.db_path.exists():
                try:
                    with open(self.db_path, "r", encoding="utf-8") as f:
                        self.users = json.load(f)
                except Exception:
                    self.users = {}
            
            # Pre-seed dedicated accounts for Traffic Management and Road Users only if missing
            demo_accounts = [
                ("admin", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                ("traffic_admin", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                ("commuter", "Admin@123", UserRole.ROAD_USER.value),
                # aliases for compatibility
                ("noc", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                ("opt", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                ("edge", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value)
            ]

            dirty = False
            for u_name, u_pass, u_role in demo_accounts:
                if u_name not in self.users:
                    p_hash, salt = hash_password(u_pass)
                    self.users[u_name] = {
                        "username": u_name,
                        "password_hash": p_hash,
                        "salt": salt,
                        "role": u_role,
                        "created_at": time.time()
                    }
                    dirty = True

            if dirty or not self.db_path.exists():
                self._save_users()

    def _save_users(self):
        with self._lock:
            atomic_json_dump(self.users, self.db_path)

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validates active bearer token session with TTL expiry check."""
        if not token:
            return None
        with self._lock:
            session = self.sessions.get(token)
            if not session:
                return None
            if time.time() - session.get("created_at", 0) > SESSION_TTL_SECONDS:
                del self.sessions[token]
                return None
            user = self.users.get(session.get("username", ""))
            if not user:
                return None
            return {**session, "role": user["role"]}

    def register(self, username: str, password: str, role: str = UserRole.ROAD_USER.value) -> tuple[bool, str]:
        username = username.strip().lower()
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters."
        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters."

        # Compute expensive cryptographic hash outside of lock to avoid thread blocking
        p_hash, salt = hash_password(password)

        if role in ["Traffic Management", "Traffic Authority"]:
            assigned_role = UserRole.TRAFFIC_MANAGEMENT.value
        else:
            assigned_role = UserRole.ROAD_USER.value

        with self._lock:
            if username in self.users:
                return False, "Username already registered."

            self.users[username] = {
                "username": username,
                "password_hash": p_hash,
                "salt": salt,
                "role": assigned_role,
                "created_at": time.time()
            }

        self._save_users()
        return True, "User registered successfully."

    def login(self, username: str, password: str) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        username = username.strip().lower()
        with self._lock:
            user = self.users.get(username)
            if not user:
                return False, "Invalid username or password.", None
            pw_hash = user["password_hash"]
            salt = user["salt"]
            role = user["role"]

        # Run constant-time PBKDF2 verification outside the lock
        if not verify_password(password, pw_hash, salt):
            return False, "Invalid username or password.", None

        token = secrets.token_urlsafe(32)
        session_info = {
            "token": token,
            "username": username,
            "role": role,
            "created_at": time.time()
        }

        with self._lock:
            self.sessions[token] = session_info
        return True, "Login successful.", session_info

    def delete_user(self, username: str) -> bool:
        username = username.strip().lower()
        with self._lock:
            if username in self.users:
                del self.users[username]
                # Also invalidate any active sessions
                self.sessions = {tok: s for tok, s in self.sessions.items() if s.get("username") != username}
                self._save_users()
                return True
        return False
