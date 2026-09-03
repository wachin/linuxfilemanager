"""Vault service for linux-file-manager."""

import base64
import hashlib
import hmac
import json
import secrets
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

from lfmapp.core.paths import VAULT_DIR


_META_FILE = ".vault_meta.json"
_LOCK_FILE = ".vault_locked"
_MARKER_FILE = ".vault"
_DATA_DIR = ".vault_data"
_PAYLOAD_MAGIC = b"LFMVAULT1\n"
_KDF_ITERATIONS = 200_000
_META_NAMES = {_MARKER_FILE, _LOCK_FILE, _META_FILE, _DATA_DIR}


class VaultService:
    """Hidden-folder vault with optional password-backed encryption."""

    def __init__(self, vault_path: Path | None = None):
        self._vault_path = Path(vault_path) if vault_path is not None else VAULT_DIR

    @property
    def vault_path(self) -> Path:
        """Return the vault directory path."""
        return self._vault_path

    def is_initialized(self) -> bool:
        """Check if the vault has been initialized."""
        return self._vault_path.exists() and self._vault_path.is_dir()

    def initialize(self, password: str | None = None, encrypted: bool = False) -> bool:
        """Initialize the vault directory."""
        try:
            self._vault_path.mkdir(parents=True, exist_ok=True)
            marker = self._vault_path / _MARKER_FILE
            marker.write_text("linux-file-manager vault\n", encoding="utf-8")
            if encrypted:
                if not password:
                    return False
                self._write_meta(self._new_meta(password))
            return True
        except OSError:
            return False

    def is_locked(self) -> bool:
        """Check if the vault is locked."""
        return not self.is_initialized() or (self._vault_path / _LOCK_FILE).exists()

    def encryption_enabled(self) -> bool:
        """Return True when the vault has encryption metadata."""
        return bool(self._read_meta().get("encrypted"))

    def enable_encryption(self, password: str) -> bool:
        """Enable password-backed encryption for an existing accessible vault."""
        if not password or not self.is_accessible():
            return False
        if self.encryption_enabled():
            return self.verify_password(password)
        try:
            self._write_meta(self._new_meta(password))
            return True
        except OSError:
            return False

    def verify_password(self, password: str) -> bool:
        """Verify a vault password without unlocking the vault."""
        meta = self._read_meta()
        if not meta.get("encrypted"):
            return True
        salt = self._decode(meta.get("salt", ""))
        expected = self._decode(meta.get("verifier", ""))
        if not salt or not expected:
            return False
        key = self._derive_key(password, salt)
        return hmac.compare_digest(self._password_verifier(key), expected)

    def lock(self, password: str | None = None) -> bool:
        """Lock the vault.

        Plain vaults use a lock marker. Encrypted vaults serialize top-level
        contents into encrypted payloads before creating the lock marker.
        """
        if not self.is_initialized():
            return False
        if self.is_locked():
            return True
        try:
            if self.encryption_enabled():
                if not password or not self.verify_password(password):
                    return False
                self._encrypt_contents(password)
            (self._vault_path / _LOCK_FILE).write_text("locked\n", encoding="utf-8")
            return True
        except OSError:
            return False

    def unlock(self, password: str | None = None) -> bool:
        """Unlock the vault."""
        lock_file = self._vault_path / _LOCK_FILE
        if self.encryption_enabled():
            if not password or not self.verify_password(password):
                return False
            try:
                self._decrypt_contents(password)
            except OSError:
                return False
        if lock_file.exists():
            lock_file.unlink()
        return True

    def is_accessible(self) -> bool:
        """Check if vault contents are accessible."""
        return self.is_initialized() and not self.is_locked()

    def list_files(self) -> list[Path]:
        """List files in the vault."""
        if not self.is_accessible():
            return []
        return [p for p in self._vault_path.iterdir() if p.name not in _META_NAMES]

    def add_file(self, source: Path) -> bool:
        """Add a file to the vault by copying it."""
        if not self.is_accessible():
            return False
        try:
            destination = self._vault_path / source.name
            if source.is_dir():
                shutil.copytree(str(source), str(destination))
            else:
                shutil.copy2(str(source), str(destination))
            return True
        except OSError:
            return False

    def move_file(self, source: Path) -> bool:
        """Move a file into the vault."""
        if not self.is_accessible():
            return False
        try:
            destination = self._vault_path / source.name
            shutil.move(str(source), str(destination))
            return True
        except OSError:
            return False

    def retrieve_file(self, filename: str, destination: Path) -> bool:
        """Copy a file from the vault to a destination."""
        if not self.is_accessible():
            return False
        source = self._vault_path / filename
        if not source.exists():
            return False
        try:
            if source.is_dir():
                shutil.copytree(str(source), str(destination / source.name))
            else:
                shutil.copy2(str(source), str(destination / source.name))
            return True
        except OSError:
            return False

    def remove_file(self, filename: str) -> bool:
        """Remove a file from the vault permanently."""
        if not self.is_accessible():
            return False
        target = self._vault_path / filename
        if not target.exists():
            return False
        try:
            if target.is_dir():
                shutil.rmtree(str(target))
            else:
                target.unlink()
            return True
        except OSError:
            return False

    def vault_size(self) -> int:
        """Get total size of vault contents in bytes."""
        if not self.is_initialized():
            return 0
        total = 0
        for item in self._vault_path.rglob("*"):
            if item.is_file() and item.name not in {_MARKER_FILE, _LOCK_FILE, _META_FILE}:
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
        return total

    def destroy_vault(self) -> bool:
        """Permanently delete the vault and all its contents."""
        if not self.is_initialized():
            return False
        try:
            shutil.rmtree(str(self._vault_path))
            return True
        except OSError:
            return False

    def _read_meta(self) -> dict:
        meta_path = self._vault_path / _META_FILE
        if not meta_path.exists():
            return {}
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_meta(self, meta: dict) -> None:
        self._vault_path.mkdir(parents=True, exist_ok=True)
        (self._vault_path / _META_FILE).write_text(
            json.dumps(meta, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _new_meta(self, password: str) -> dict:
        salt = secrets.token_bytes(16)
        key = self._derive_key(password, salt)
        return {
            "version": 1,
            "encrypted": True,
            "kdf": "pbkdf2_hmac_sha256",
            "iterations": _KDF_ITERATIONS,
            "salt": self._encode(salt),
            "verifier": self._encode(self._password_verifier(key)),
            "files": [],
        }

    def _encrypt_contents(self, password: str) -> None:
        meta = self._read_meta()
        key = self._key_from_meta(password, meta)
        data_dir = self._vault_path / _DATA_DIR
        if data_dir.exists():
            shutil.rmtree(str(data_dir))
        data_dir.mkdir()

        files = []
        for item in list(self._vault_path.iterdir()):
            if item.name in _META_NAMES:
                continue
            payload = self._pack_item(item)
            payload_name = f"{secrets.token_hex(16)}.lfmvault"
            (data_dir / payload_name).write_bytes(self._encrypt_payload(key, payload))
            files.append({"name": item.name, "payload": payload_name})
            self._remove_item(item)

        meta["files"] = files
        self._write_meta(meta)

    def _decrypt_contents(self, password: str) -> None:
        meta = self._read_meta()
        key = self._key_from_meta(password, meta)
        data_dir = self._vault_path / _DATA_DIR
        for entry in meta.get("files", []):
            if not isinstance(entry, dict):
                continue
            payload_name = entry.get("payload")
            if not isinstance(payload_name, str):
                continue
            payload_path = data_dir / Path(payload_name).name
            if not payload_path.exists():
                continue
            self._unpack_item(self._decrypt_payload(key, payload_path.read_bytes()))

        if data_dir.exists():
            shutil.rmtree(str(data_dir))
        meta["files"] = []
        self._write_meta(meta)

    def _pack_item(self, item: Path) -> bytes:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if item.is_dir():
                archive.write(item, f"{item.name}/")
                for child in item.rglob("*"):
                    archive.write(child, child.relative_to(item.parent).as_posix())
            else:
                archive.write(item, item.name)
        return buffer.getvalue()

    def _unpack_item(self, payload: bytes) -> None:
        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            base = self._vault_path.resolve()
            for member in archive.infolist():
                target = (self._vault_path / member.filename).resolve()
                if not self._is_relative_to(target, base):
                    raise OSError("Encrypted vault payload contains an unsafe path")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)

    def _encrypt_payload(self, key: bytes, payload: bytes) -> bytes:
        nonce = secrets.token_bytes(16)
        ciphertext = self._xor_stream(payload, key, nonce)
        signature = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
        return _PAYLOAD_MAGIC + nonce + signature + ciphertext

    def _decrypt_payload(self, key: bytes, payload: bytes) -> bytes:
        if not payload.startswith(_PAYLOAD_MAGIC):
            raise OSError("Unsupported encrypted vault payload")
        offset = len(_PAYLOAD_MAGIC)
        nonce = payload[offset : offset + 16]
        signature = payload[offset + 16 : offset + 48]
        ciphertext = payload[offset + 48 :]
        expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise OSError("Encrypted vault payload authentication failed")
        return self._xor_stream(ciphertext, key, nonce)

    def _key_from_meta(self, password: str, meta: dict) -> bytes:
        salt = self._decode(meta.get("salt", ""))
        if not salt:
            raise OSError("Encrypted vault metadata is missing its salt")
        return self._derive_key(password, salt)

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            _KDF_ITERATIONS,
            dklen=32,
        )

    @staticmethod
    def _password_verifier(key: bytes) -> bytes:
        return hmac.new(key, b"linux-file-manager-vault", hashlib.sha256).digest()

    @staticmethod
    def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
        output = bytearray()
        counter = 0
        for offset in range(0, len(data), hashlib.sha256().digest_size):
            block = hmac.new(
                key,
                nonce + counter.to_bytes(8, "big"),
                hashlib.sha256,
            ).digest()
            chunk = data[offset : offset + len(block)]
            output.extend(byte ^ mask for byte, mask in zip(chunk, block))
            counter += 1
        return bytes(output)

    @staticmethod
    def _encode(data: bytes) -> str:
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _decode(data: str) -> bytes:
        try:
            return base64.b64decode(data.encode("ascii"))
        except (ValueError, UnicodeEncodeError):
            return b""

    @staticmethod
    def _remove_item(item: Path) -> None:
        if item.is_dir():
            shutil.rmtree(str(item))
        else:
            item.unlink()

    @staticmethod
    def _is_relative_to(path: Path, base: Path) -> bool:
        try:
            path.relative_to(base)
            return True
        except ValueError:
            return False
