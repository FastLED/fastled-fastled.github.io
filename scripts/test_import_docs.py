"""Exercise real documentation archives and HTTP publication checks."""

import hashlib
import io
import json
import tarfile
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from import_docs import check_publication, stage_archive, validate_manifest


class DocumentationImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / "site"
        (self.site / "docs").mkdir(parents=True)
        (self.site / "docs/index.html").write_text("old redirect")
        self.release = {
            "id": 416153555,
            "tag_name": "3.10.8",
            "source_sha": "d7402f1294e4548d9f8317f76afad37afaddb237",
            "doxygen_version": "1.13.2",
            "generation": "123-1",
        }
        self.manifest = {
            "schema_version": 1,
            "generation": "123-1",
            "release": self.release,
            "archive": {
                "url": "https://github.com/FastLED/dox/releases/download/docs-123-1/docs.tar.gz",
                "sha256": "",
                "size": 0,
            },
        }
        self.archive = self.root / "docs.tar.gz"
        self.make_archive()

    def make_archive(self, extra=None):
        files = {
            "./index.html": b"<h1>FastLED documentation</h1>",
            "./annotated.html": b"<h1>Classes</h1>",
            "./search/search.js": b"search works",
            "./release.json": json.dumps(self.release).encode(),
        }
        with tarfile.open(self.archive, "w:gz") as tar:
            for name, content in files.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(content)
                tar.addfile(entry, io.BytesIO(content))
            if extra is not None:
                tar.addfile(extra, io.BytesIO(b"bad") if extra.isfile() else None)
        self.manifest["archive"]["sha256"] = hashlib.sha256(
            self.archive.read_bytes()
        ).hexdigest()
        self.manifest["archive"]["size"] = self.archive.stat().st_size

    def test_import_replaces_redirect_and_preserves_site(self):
        (self.site / "index.html").write_text("homepage")
        stage_archive(self.archive, self.site, self.manifest)
        self.assertIn(
            "FastLED documentation", (self.site / "docs/index.html").read_text()
        )
        self.assertEqual((self.site / "index.html").read_text(), "homepage")
        self.assertEqual(
            json.loads((self.site / "docs/publication.json").read_text()), self.manifest
        )
        self.assertEqual(
            json.loads((self.site / "docs/release.json").read_text()), self.release
        )
        self.assertTrue((self.site / "docs/search/search.js").is_file())

    def test_checksum_failure_preserves_existing_docs(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"tampered")
        with self.assertRaises(ValueError):
            stage_archive(self.archive, self.site, self.manifest)
        self.assertEqual((self.site / "docs/index.html").read_text(), "old redirect")

    def test_paths_and_links_cannot_escape_docs(self):
        for name, kind in [("../outside", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)]:
            with self.subTest(name=name):
                extra = tarfile.TarInfo(name)
                extra.type = kind
                extra.linkname = "/tmp/outside"
                extra.size = 3 if kind == tarfile.REGTYPE else 0
                self.make_archive(extra)
                with self.assertRaises(ValueError):
                    stage_archive(self.archive, self.site, self.manifest)
                self.assertFalse((self.root / "outside").exists())
                self.assertEqual(
                    (self.site / "docs/index.html").read_text(), "old redirect"
                )

    def test_source_metadata_mismatch_preserves_existing_docs(self):
        self.manifest["release"] = {**self.release, "source_sha": "0" * 40}
        with self.assertRaises(ValueError):
            stage_archive(self.archive, self.site, self.manifest)
        self.assertEqual((self.site / "docs/index.html").read_text(), "old redirect")

    def test_manifest_rejects_foreign_asset_and_generation_mismatch(self):
        validate_manifest(self.manifest)
        bad = json.loads(json.dumps(self.manifest))
        bad["archive"]["url"] = "https://example.org/docs.tar.gz"
        with self.assertRaises(ValueError):
            validate_manifest(bad)
        bad = json.loads(json.dumps(self.manifest))
        bad["release"]["generation"] = "124-1"
        with self.assertRaises(ValueError):
            validate_manifest(bad)

    def test_actual_http_checks_skip_unchanged_and_detect_same_tag_rebuild(self):
        handler = partial(SimpleHTTPRequestHandler, directory=str(self.root))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        (self.root / "upstream.json").write_text(json.dumps(self.manifest))
        source, changed = check_publication(
            base + "/upstream.json", base + "/missing.json"
        )
        self.assertTrue(changed)
        self.assertEqual(source, self.manifest)
        (self.root / "current.json").write_text(json.dumps(self.manifest))
        _, changed = check_publication(base + "/upstream.json", base + "/current.json")
        self.assertFalse(changed)
        updated = json.loads(json.dumps(self.manifest))
        updated["generation"] = updated["release"]["generation"] = "123-2"
        updated["archive"]["url"] = updated["archive"]["url"].replace("123-1", "123-2")
        (self.root / "upstream.json").write_text(json.dumps(updated))
        _, changed = check_publication(base + "/upstream.json", base + "/current.json")
        self.assertTrue(changed)
        (self.root / "current.json").write_text("not JSON")
        _, changed = check_publication(base + "/upstream.json", base + "/current.json")
        self.assertTrue(changed)
        (self.root / "upstream.json").write_text("not JSON")
        with self.assertRaises(ValueError):
            check_publication(base + "/upstream.json", base + "/current.json")


if __name__ == "__main__":
    unittest.main()
