import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
from django.test import SimpleTestCase
from cryptography.exceptions import InvalidTag
from university.operations.backup import encrypt_bundle, extract_bundle


class EncryptedBackupTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "database.sql").write_text("CREATE TABLE synthetic(id INT);")
        with tarfile.open(self.source / "media.tar", "w") as archive:
            data = b"Synthetic private document"
            item = tarfile.TarInfo("document.txt")
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
        self.manifest()
        self.key = self.root / "recovery.key"
        self.key.write_bytes(os.urandom(32))
        self.key.chmod(0o600)
        self.output = self.root / "encrypted.hrbackup"

    def manifest(self):
        hashes = {}
        for name in ("database.sql", "media.tar"):
            hashes[name] = hashlib.sha256((self.source / name).read_bytes()).hexdigest()
        (self.source / "manifest.json").write_text(json.dumps({"sha256": hashes}))

    def test_roundtrip_keeps_database_and_media_and_refuses_overwrite(self):
        encrypt_bundle(self.source, self.output, self.key)
        self.assertNotIn(b"Synthetic private document", self.output.read_bytes())
        target = self.root / "restored"
        extract_bundle(self.output, target, self.key)
        for name in ("database.sql", "media.tar"):
            self.assertEqual(
                (target / name).read_bytes(), (self.source / name).read_bytes()
            )
        with self.assertRaises(ValueError):
            extract_bundle(self.output, target, self.key)
        with self.assertRaises(ValueError):
            encrypt_bundle(self.source, self.output, self.key)

    def test_wrong_key_and_tampering_create_no_restore_directory(self):
        encrypt_bundle(self.source, self.output, self.key)
        original = self.output.read_bytes()
        bad = bytearray(original)
        bad[len(bad) // 2] ^= 1
        self.output.write_bytes(bad)
        target = self.root / "restored"
        with self.assertRaises(InvalidTag):
            extract_bundle(self.output, target, self.key)
        self.assertFalse(target.exists())
        self.output.write_bytes(original)
        self.key.write_bytes(os.urandom(32))
        with self.assertRaises(InvalidTag):
            extract_bundle(self.output, target, self.key)
        self.assertFalse(target.exists())

    def test_media_traversal_and_links_are_rejected_after_authentication(self):
        for name, kind in (
            ("../outside.txt", tarfile.REGTYPE),
            ("link", tarfile.SYMTYPE),
        ):
            with self.subTest(name=name):
                self.output.unlink(missing_ok=True)
                with tarfile.open(self.source / "media.tar", "w") as archive:
                    item = tarfile.TarInfo(name)
                    item.type = kind
                    item.linkname = "/etc/passwd"
                    item.size = 0
                    archive.addfile(item)
                self.manifest()
                encrypt_bundle(self.source, self.output, self.key)
                target = self.root / "restored"
                with self.assertRaises(ValueError):
                    extract_bundle(self.output, target, self.key)
                self.assertFalse(target.exists())

    def test_unsafe_key_permissions_are_rejected(self):
        self.key.chmod(0o644)
        with self.assertRaises(ValueError):
            encrypt_bundle(self.source, self.output, self.key)
