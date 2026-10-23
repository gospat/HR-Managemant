"""Authenticated streaming backups. Decrypt/authenticate before parsing archives."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"BELLS-HR-BACKUP-1\n"
CHUNK = 1024 * 1024


def read_key(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise ValueError("Backup key must be readable by its owner only (0600).")
    key = path.read_bytes()
    if len(key) != 32:
        raise ValueError("Backup key must contain exactly 32 random bytes.")
    return key


def encrypt_bundle(source, output, key_path):
    source, output = Path(source), Path(output)
    files = ("database.sql", "media.tar", "manifest.json")
    if not all(
        (source / name).is_file() and not (source / name).is_symlink() for name in files
    ):
        raise ValueError("A complete database/media/manifest bundle is required.")
    key = read_key(key_path)
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    cipher.authenticate_additional_data(MAGIC)
    try:
        with output.open("xb") as destination:
            output.chmod(0o600)
            destination.write(MAGIC + nonce)

            class Writer:
                def write(self, data):
                    destination.write(cipher.update(data))
                    return len(data)

            with tarfile.open(fileobj=Writer(), mode="w|") as archive:
                for name in files:
                    archive.add(source / name, arcname=name, recursive=False)
            destination.write(cipher.finalize())
            destination.write(cipher.tag)
            destination.flush()
            os.fsync(destination.fileno())
    except FileExistsError:
        raise ValueError("Refusing to overwrite an existing backup.")
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def extract_bundle(source, destination, key_path):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError("Restore destination must not already exist.")
    key = read_key(key_path)
    with tempfile.TemporaryDirectory() as private:
        plaintext = Path(private) / "verified.tar"
        with source.open("rb") as encrypted:
            if encrypted.read(len(MAGIC)) != MAGIC:
                raise ValueError("Invalid backup format.")
            nonce = encrypted.read(12)
            remaining = source.stat().st_size - len(MAGIC) - 12 - 16
            if remaining < 0:
                raise ValueError("Truncated backup.")
            encrypted.seek(-16, 2)
            tag = encrypted.read(16)
            encrypted.seek(len(MAGIC) + 12)
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(MAGIC)
            with plaintext.open("xb") as out:
                plaintext.chmod(0o600)
                while remaining:
                    block = encrypted.read(min(CHUNK, remaining))
                    if not block:
                        raise ValueError("Truncated backup.")
                    remaining -= len(block)
                    out.write(decryptor.update(block))
                # No archive is parsed or destination created before authentication.
                out.write(decryptor.finalize())
        with tarfile.open(plaintext) as archive:
            entries = archive.getmembers()
            names = {"database.sql", "media.tar", "manifest.json"}
            if (
                len(entries) != 3
                or {entry.name for entry in entries} != names
                or any(not entry.isfile() for entry in entries)
            ):
                raise ValueError("Unexpected backup members.")
            staging = Path(private) / "files"
            staging.mkdir(mode=0o700)
            for entry in entries:
                with archive.extractfile(entry) as src, (staging / entry.name).open(
                    "xb"
                ) as target:
                    shutil.copyfileobj(src, target, CHUNK)
                (staging / entry.name).chmod(0o600)
        manifest = json.loads((staging / "manifest.json").read_text())
        if not isinstance(manifest, dict) or not isinstance(
            manifest.get("sha256"), dict
        ):
            raise ValueError("Invalid backup manifest.")
        for name in ("database.sql", "media.tar"):
            with (staging / name).open("rb") as verified_file:
                digest = hashlib.file_digest(verified_file, "sha256").hexdigest()
            if manifest.get("sha256", {}).get(name) != digest:
                raise ValueError("Backup content checksum does not match.")
        with tarfile.open(staging / "media.tar") as media:
            for entry in media:
                parts = Path(entry.name).parts
                if (
                    entry.name.startswith("/")
                    or ".." in parts
                    or not (entry.isfile() or entry.isdir())
                ):
                    raise ValueError("Unsafe media archive member.")
        destination.mkdir(mode=0o700, parents=False)
        for name in names:
            shutil.copyfile(staging / name, destination / name)
            (destination / name).chmod(0o600)
