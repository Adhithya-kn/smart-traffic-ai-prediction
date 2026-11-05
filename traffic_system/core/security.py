"""
traffic_system/core/security.py - Authentication, Password Hashing & Role-Based Access Control
Production-grade security module with Fast Cache duplicate-submission prevention,
strict role escalation defense, credential criteria threshold validation, and
secure session management.
"""

import os
import re
import json
import hashlib
import secrets
import time
import threading
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path

from traffic_system.config import (
    USERS_DB_PATH,
    SESSIONS_DB_PATH,
    ALLOW_DEMO_ACCOUNTS,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    SESSION_TTL_SECONDS,
    IS_PRODUCTION
)
from traffic_system.core.entities import UserRole
from traffic_system.core.fs_utils import atomic_json_dump, safe_read_json
from traffic_system.storage.migrations import migrate_users_data, migrate_sessions_data

ITERATIONS = 20_000

MIN_USERNAME_LEN = 3
MAX_USERNAME_LEN = 32
MIN_PASSWORD_LEN = 6
MAX_PASSWORD_LEN = 128
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]+$")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 60.0
INFLIGHT_COOLDOWN_SECONDS = 1.0
CACHE_RESULT_TTL_SECONDS = 2.5


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Hashes a password with PBKDF2-HMAC-SHA256 and a 16-byte random salt.
    Zero external C-dependencies; standard constant-time cryptographic verification.
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


def sanitize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """Strips confidential hash and salt values from public/API representations."""
    safe = dict(user)
    safe.pop("password_hash", None)
    safe.pop("salt", None)
    return safe


class RateLimiter:
    """
    Sliding window rate limiter tracking request frequencies per identifier.
    Thread-safe and low-overhead.
    """
    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> Tuple[bool, int]:
        now = time.time()
        with self._lock:
            timestamps = self._history.get(key, [])
            timestamps = [ts for ts in timestamps if now - ts < self.window_seconds]
            if len(timestamps) >= self.max_requests:
                oldest = timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                self._history[key] = timestamps
                return False, retry_after

            timestamps.append(now)
            self._history[key] = timestamps
            return True, 0

    def reset(self):
        with self._lock:
            self._history.clear()


class SecurityManager:
    """
    Manages user registration, login, and active token sessions.
    Includes in-memory Fast Cache for rapid double-submission deduplication,
    brute-force rate limiting thresholds, and strict credential validation.
    """
    def __init__(self, db_path: Path = USERS_DB_PATH, sessions_db_path: Path = SESSIONS_DB_PATH):
        self.db_path = Path(db_path)
        self.sessions_db_path = Path(sessions_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.users: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

        self._inflight: Dict[str, float] = {}
        self._recent_success: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._failed_attempts: Dict[str, List[float]] = {}

        self.upload_limiter = RateLimiter(max_requests=10, window_seconds=60.0)
        self.chunk_limiter = RateLimiter(max_requests=120, window_seconds=60.0)
        self.process_limiter = RateLimiter(max_requests=10, window_seconds=60.0)
        self.live_refresh_limiter = RateLimiter(max_requests=5, window_seconds=60.0)

        self._load_users()
        self._load_sessions()

    def check_rate_limit(self, action: str, identifier: str) -> Tuple[bool, int]:
        """
        Evaluates action rate limit for given user or IP identifier.
        Returns (is_allowed, retry_after_seconds).
        """
        if action == "upload":
            return self.upload_limiter.check(identifier)
        elif action == "chunk_upload":
            return self.chunk_limiter.check(identifier)
        elif action == "process":
            return self.process_limiter.check(identifier)
        elif action == "live_refresh":
            return self.live_refresh_limiter.check(identifier)
        return True, 0

    def _clean_fast_cache(self, now: float):
        """Thread-safe background pruning of stale fast cache and lockout entries."""
        self._inflight = {k: ts for k, ts in self._inflight.items() if now - ts < 10.0}
        self._recent_success = {k: v for k, v in self._recent_success.items() if now - v[0] < 10.0}
        self._failed_attempts = {
            k: [ts for ts in tss if now - ts < LOCKOUT_WINDOW_SECONDS]
            for k, tss in self._failed_attempts.items()
        }
        self._failed_attempts = {k: v for k, v in self._failed_attempts.items() if v}

    @staticmethod
    def validate_credentials(username: str, password: str) -> Tuple[bool, str]:
        """Validates username and password criteria against strict production thresholds."""
        u = str(username).strip()
        p = str(password).strip()

        if not u:
            return False, "Username cannot be empty."
        if len(u) < MIN_USERNAME_LEN or len(u) > MAX_USERNAME_LEN:
            return False, f"Username must be between {MIN_USERNAME_LEN} and {MAX_USERNAME_LEN} characters."
        if not USERNAME_REGEX.match(u):
            return False, "Username may only contain letters, numbers, underscores, dots, or hyphens."
        if not p:
            return False, "Password cannot be empty."
        if len(p) < MIN_PASSWORD_LEN:
            return False, f"Password must be at least {MIN_PASSWORD_LEN} characters."
        if len(p) > MAX_PASSWORD_LEN:
            return False, f"Password cannot exceed {MAX_PASSWORD_LEN} characters."

        return True, "Valid"

    def _load_users(self):
        with self._lock:
            if self.db_path.exists():
                try:
                    with open(self.db_path, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    self.users, migrated = migrate_users_data(raw_data)
                except Exception:
                    self.users, migrated = {}, False
            else:
                self.users = {}
                migrated = False

            dirty = migrated

            # Provision administrator from environment if defined
            if ADMIN_USERNAME and ADMIN_PASSWORD:
                p_hash, salt = hash_password(ADMIN_PASSWORD)
                self.users[ADMIN_USERNAME.lower()] = {
                    "username": ADMIN_USERNAME.lower(),
                    "password_hash": p_hash,
                    "salt": salt,
                    "role": UserRole.TRAFFIC_MANAGEMENT.value,
                    "created_at": time.time(),
                    "is_active": True,
                    "schema_version": 2
                }
                dirty = True

            if ALLOW_DEMO_ACCOUNTS and not IS_PRODUCTION:
                # Seed development demo accounts only when permitted in non-production
                demo_accounts = [
                    ("admin", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                    ("traffic_admin", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                    ("operator", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                    ("commuter", "Admin@123", UserRole.ROAD_USER.value),
                    ("noc", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                    ("opt", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value),
                    ("edge", "Admin@123", UserRole.TRAFFIC_MANAGEMENT.value)
                ]
                for u_name, u_pass, u_role in demo_accounts:
                    if u_name not in self.users:
                        p_hash, salt = hash_password(u_pass)
                        self.users[u_name] = {
                            "username": u_name,
                            "password_hash": p_hash,
                            "salt": salt,
                            "role": u_role,
                            "created_at": time.time(),
                            "is_active": True,
                            "schema_version": 2
                        }
                        dirty = True

            if dirty or not self.db_path.exists():
                self._save_users()

    def _load_sessions(self):
        with self._lock:
            if self.sessions_db_path.exists():
                raw = safe_read_json(self.sessions_db_path, {})
                migrated_sessions, was_modified = migrate_sessions_data(raw)
                # Prune expired sessions against active TTL
                now = time.time()
                active = {}
                for tok, s in migrated_sessions.items():
                    if (now - s.get("created_at", 0)) <= SESSION_TTL_SECONDS:
                        active[tok] = s
                    else:
                        was_modified = True
                self.sessions = active
                if was_modified or not self.sessions_db_path.exists():
                    self._save_sessions()
            else:
                self.sessions = {}

    def _save_users(self):
        with self._lock:
            atomic_json_dump(self.users, self.db_path)

    def _save_sessions(self):
        with self._lock:
            atomic_json_dump(self.sessions, self.sessions_db_path)

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
                self._save_sessions()
                return None
            user = self.users.get(session.get("username", ""))
            if not user:
                return None
            return {
                "token": token,
                "username": user["username"],
                "role": user["role"],
                "created_at": session.get("created_at")
            }

    def register(
        self,
        username: str,
        password: str,
        role: str = UserRole.ROAD_USER.value,
        is_admin_invoker: bool = False
    ) -> Tuple[bool, str]:
        """
        Registers a new user account with strict criteria validation.
        PUBLIC REGISTRATION CANNOT ELEVATE TO ADMINISTRATOR:
        Public users are strictly assigned UserRole.ROAD_USER.value unless
        the invoker is already an authenticated administrator.
        """
        valid, msg = self.validate_credentials(username, password)
        if not valid:
            return False, msg

        username = username.strip().lower()
        p_hash, salt = hash_password(password)

        # Privilege escalation prevention:
        # Public users cannot register as Traffic Management
        if is_admin_invoker and role in ["Traffic Management", "Traffic Authority", "Management"]:
            assigned_role = UserRole.TRAFFIC_MANAGEMENT.value
        else:
            # All public registrations are assigned ROAD_USER regardless of requested role
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

    def login(self, username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Production login with:
        1. Strict username & password criteria checking
        2. Fast Cache double-entry & in-flight deduplication
        3. Brute-force rate limiting threshold lockout
        4. Constant-time cryptographic verification
        """
        valid, err_msg = self.validate_credentials(username, password)
        if not valid:
            return False, err_msg, None

        norm_user = username.strip().lower()
        now = time.time()
        pw_fingerprint = hashlib.sha256(password.encode("utf-8")).hexdigest()[:16]
        cache_key = f"{norm_user}:{pw_fingerprint}"

        with self._lock:
            self._clean_fast_cache(now)

            failures = self._failed_attempts.get(norm_user, [])
            if len(failures) >= MAX_FAILED_ATTEMPTS:
                oldest_failure = failures[0]
                cooldown_remaining = int(LOCKOUT_WINDOW_SECONDS - (now - oldest_failure))
                if cooldown_remaining > 0:
                    return False, f"Too many failed attempts. Temporary lockout active. Please wait {cooldown_remaining}s.", None
                else:
                    self._failed_attempts.pop(norm_user, None)

            if norm_user in self._inflight:
                delta = now - self._inflight[norm_user]
                if delta < INFLIGHT_COOLDOWN_SECONDS:
                    return False, "Duplicate submission detected. Please wait a moment.", None

            if cache_key in self._recent_success:
                cached_time, cached_session = self._recent_success[cache_key]
                if now - cached_time < CACHE_RESULT_TTL_SECONDS:
                    return True, "Login successful.", cached_session

            user = self.users.get(norm_user)
            if not user:
                self._failed_attempts.setdefault(norm_user, []).append(now)
                return False, "Invalid username or password.", None

            pw_hash = user["password_hash"]
            salt = user["salt"]
            role = user["role"]

            self._inflight[norm_user] = now

        try:
            pw_matches = verify_password(password, pw_hash, salt)
        finally:
            with self._lock:
                self._inflight.pop(norm_user, None)

        now = time.time()
        if not pw_matches:
            with self._lock:
                self._failed_attempts.setdefault(norm_user, []).append(now)
            return False, "Invalid username or password.", None

        token = secrets.token_urlsafe(32)
        session_info = {
            "token": token,
            "username": norm_user,
            "role": role,
            "created_at": now
        }

        with self._lock:
            self._failed_attempts.pop(norm_user, None)
            self.sessions[token] = session_info
            self._recent_success[cache_key] = (now, session_info)
            self._save_sessions()

        return True, "Login successful.", session_info

    def logout(self, token: str) -> bool:
        """Revokes an active session token."""
        with self._lock:
            if token in self.sessions:
                sess = self.sessions.pop(token)
                uname = sess.get("username")
                if uname:
                    self._recent_success = {k: v for k, v in self._recent_success.items() if not k.startswith(f"{uname}:")}
                self._save_sessions()
                return True
        return False

    def delete_user(self, username: str) -> bool:
        """Deletes user and flushes their active sessions."""
        username = username.strip().lower()
        with self._lock:
            if username in self.users:
                del self.users[username]
                self.sessions = {tok: s for tok, s in self.sessions.items() if s.get("username") != username}
                self._failed_attempts.pop(username, None)
                self._recent_success = {k: v for k, v in self._recent_success.items() if not k.startswith(f"{username}:")}
                self._inflight.pop(username, None)
                self._save_users()
                self._save_sessions()
                return True
        return False
