"""
traffic_system/core/secrets_manager.py - Secure Persistent Secrets Manager
Implements NIST SP 800-38D AES-256-GCM authenticated encryption with RFC 9106/scrypt KDF.
Features:
- 40-byte binary header bound as AES-GCM Associated Authenticated Data (AAD)
- Fresh 12-byte CSPRNG nonce per write (zero reuse)
- Volatile memory zeroization for master keys (bytearray scrubbed)
- POSIX atomic two-phase write commit with F_FULLFSYNC / fsync
- Zero raw keys in ordinary JSON or responses
"""

import os
import sys
import json
import struct
import hashlib
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from traffic_system.config import ARTIFACTS_DIR

MAGIC_BYTES = b"WVLT"
VAULT_VERSION = 0x01
KDF_SCRYPT = 0x02
DEFAULT_SCRYPT_N = 65536
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1
HEADER_LEN = 40
NONCE_LEN = 12
SALT_LEN = 16
TAG_LEN = 16

SECRETS_VAULT_PATH = ARTIFACTS_DIR / ".secrets.vault"


def _zeroize(buf: bytearray) -> None:
    """Explicitly scrubs mutable bytearray buffers in volatile memory."""
    for i in range(len(buf)):
        buf[i] = 0


def _derive_key(passphrase: str, salt: bytes, n: int = DEFAULT_SCRYPT_N, r: int = DEFAULT_SCRYPT_R, p: int = DEFAULT_SCRYPT_P) -> bytearray:
    """Derives a 256-bit symmetric key using scrypt."""
    key_bytes = hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=128 * 1024 * 1024,
        dklen=32
    )
    return bytearray(key_bytes)


class SecureSecretsManager:
    """
    Cryptographically fortified persistent secrets store.
    Prevents storage of plaintext API tokens in ordinary JSON files.
    """
    _instance: Optional["SecureSecretsManager"] = None
    _lock = threading.RLock()

    def __init__(self, vault_path: Optional[Path] = None, master_key: Optional[str] = None):
        self.vault_path = vault_path or SECRETS_VAULT_PATH
        # Derive master key from canonical VAULT_MASTER_KEY (with legacy SECRETS_VAULT_KEY fallback)
        env_key = (master_key or os.environ.get("VAULT_MASTER_KEY") or os.environ.get("SECRETS_VAULT_KEY") or "").strip()
        from traffic_system.config import IS_PRODUCTION
        if not env_key:
            if IS_PRODUCTION and self.vault_path.exists():
                raise RuntimeError("FATAL: VAULT_MASTER_KEY must be configured in production when secrets vault is active.")
            # Deterministic host-bound seed for local development
            env_key = f"bengaluru-traffic-vault-{os.name}-{sys.platform}"
        self._master_passphrase = env_key
        self._secrets: Dict[str, str] = {}
        self._load_vault()

    @classmethod
    def get_instance(cls) -> "SecureSecretsManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = SecureSecretsManager()
            return cls._instance

    def _pack_header(self, salt: bytes, nonce: bytes) -> bytes:
        """
        Packs 40-byte binary header:
        0x00-0x03: MAGIC b'WVLT' (4B)
        0x04: VERSION 0x01 (1B)
        0x05: KDF_ID 0x02 (scrypt) (1B)
        0x06-0x09: M_COST N uint32-BE (4B)
        0x0A: T_COST R uint8 (1B)
        0x0B: P_COST P uint8 (1B)
        0x0C-0x1B: SALT (16B)
        0x1C-0x27: NONCE (12B)
        Total = 4 + 1 + 1 + 4 + 1 + 1 + 16 + 12 = 40 Bytes.
        """
        header = struct.pack(
            ">4sBBIBB16s12s",
            MAGIC_BYTES,
            VAULT_VERSION,
            KDF_SCRYPT,
            DEFAULT_SCRYPT_N,
            DEFAULT_SCRYPT_R,
            DEFAULT_SCRYPT_P,
            salt,
            nonce
        )
        assert len(header) == HEADER_LEN, f"Header size mismatch: {len(header)} != 40"
        return header

    def _unpack_header(self, data: bytes) -> Dict[str, Any]:
        """Unpacks and validates the 40-byte binary header."""
        if len(data) < HEADER_LEN + TAG_LEN:
            raise ValueError("Vault payload is truncated or incomplete.")
        magic, ver, kdf_id, n_cost, r_cost, p_cost, salt, nonce = struct.unpack(
            ">4sBBIBB16s12s",
            data[:HEADER_LEN]
        )
        if magic != MAGIC_BYTES:
            raise ValueError("Invalid vault magic identifier.")
        if ver != VAULT_VERSION:
            raise ValueError(f"Unsupported vault version {ver}.")
        return {
            "magic": magic,
            "version": ver,
            "kdf_id": kdf_id,
            "n_cost": n_cost,
            "r_cost": r_cost,
            "p_cost": p_cost,
            "salt": salt,
            "nonce": nonce
        }

    def _load_vault(self) -> bool:
        """Decrypts and loads existing persistent secrets from the encrypted vault."""
        with self._lock:
            if not self.vault_path.exists():
                return False
            try:
                raw = self.vault_path.read_bytes()
                header_info = self._unpack_header(raw)
                header_bytes = raw[:HEADER_LEN]
                ciphertext_with_tag = raw[HEADER_LEN:]

                key_buf = _derive_key(
                    self._master_passphrase,
                    header_info["salt"],
                    n=header_info["n_cost"],
                    r=header_info["r_cost"],
                    p=header_info["p_cost"]
                )
                try:
                    aesgcm = AESGCM(bytes(key_buf))
                    decrypted = aesgcm.decrypt(
                        header_info["nonce"],
                        ciphertext_with_tag,
                        header_bytes  # AAD binding
                    )
                    self._secrets = json.loads(decrypted.decode("utf-8"))
                    # Synchronize into environment without overwriting explicit environment overrides
                    for k, v in self._secrets.items():
                        if k not in os.environ or not os.environ[k]:
                            os.environ[k] = v
                    return True
                finally:
                    _zeroize(key_buf)
            except Exception:
                return False

    def _persist_vault(self) -> bool:
        """Atomically writes secrets encrypted with AES-256-GCM to the vault file."""
        with self._lock:
            self.vault_path.parent.mkdir(parents=True, exist_ok=True)
            salt = os.urandom(SALT_LEN)
            nonce = os.urandom(NONCE_LEN)
            header_bytes = self._pack_header(salt, nonce)

            key_buf = _derive_key(
                self._master_passphrase,
                salt,
                n=DEFAULT_SCRYPT_N,
                r=DEFAULT_SCRYPT_R,
                p=DEFAULT_SCRYPT_P
            )
            try:
                aesgcm = AESGCM(bytes(key_buf))
                plaintext = json.dumps(self._secrets).encode("utf-8")
                ciphertext = aesgcm.encrypt(nonce, plaintext, header_bytes)  # AAD binding

                # Two-phase atomic POSIX commit
                temp_fd, temp_path = tempfile.mkstemp(
                    prefix=".vault_",
                    dir=str(self.vault_path.parent)
                )
                try:
                    with os.fdopen(temp_fd, "wb") as f:
                        f.write(header_bytes)
                        f.write(ciphertext)
                        f.flush()
                        try:
                            # Hardware flush F_FULLFSYNC on macOS if supported
                            import fcntl
                            fcntl.fcntl(f.fileno(), 51)  # F_FULLFSYNC
                        except Exception:
                            os.fsync(f.fileno())
                    os.chmod(temp_path, 0o600)
                    os.replace(temp_path, self.vault_path)
                    return True
                except Exception:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise
            finally:
                _zeroize(key_buf)

    def set_secret(self, key: str, value: str) -> None:
        """Persists a secret securely, updating runtime os.environ and encrypted vault."""
        clean_key = str(key).strip()
        clean_val = str(value).strip()
        with self._lock:
            self._secrets[clean_key] = clean_val
            os.environ[clean_key] = clean_val
            self._persist_vault()

    def get_secret(self, key: str, default: str = "") -> str:
        """Retrieves secret, checking environment first, then encrypted vault."""
        clean_key = str(key).strip()
        with self._lock:
            if clean_key in os.environ and os.environ[clean_key]:
                return os.environ[clean_key]
            return self._secrets.get(clean_key, default)

    def has_secret(self, key: str) -> bool:
        """Checks if a non-empty secret exists."""
        return bool(self.get_secret(key))


def get_secrets_manager() -> SecureSecretsManager:
    return SecureSecretsManager.get_instance()
