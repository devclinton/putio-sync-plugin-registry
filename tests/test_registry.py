"""Tests for scripts/registry.py. Standard library only:

    python3 -m unittest discover -s tests
"""

import hashlib
import importlib.util
import io
import tarfile
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("registry", ROOT / "scripts" / "registry.py")
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)

MANIFEST = """\
name = "webhook-notifier"
version = "1.0.0"
description = "POST a small JSON message to a webhook"
events = ["download.finished", "download.failed"]
author = "devclinton"
license = "MIT"
repository = "https://github.com/devclinton/putio-sync-plugin-registry"

[permissions.http]
host_from_config = ["url"]
"""

URL = "https://example.com/webhook-notifier-1.0.0.tar.gz"


def archive(files, links=()):
    """A .tar.gz holding `files` ({path: text}) and symbolic `links` ({path: target})."""
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as t:
        for name, text in files.items():
            body = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(body)
            t.addfile(info, io.BytesIO(body))
        for name, target in dict(links).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            t.addfile(info)
    return out.getvalue()


def good_files(manifest=MANIFEST):
    return {"webhook-notifier/plugin.toml": manifest, "webhook-notifier/main.lua": "return {}\n"}


def entry():
    path = ROOT / "examples" / "entries" / "webhook-notifier.toml"
    return path, tomllib.loads(path.read_text())


def wasm_module(manifest):
    """A module holding only a putio-plugin custom section (one-byte LEB128 sizes)."""
    name = registry.WASM_SECTION
    payload = bytes([len(name)]) + name + manifest.encode()
    assert len(payload) < 128
    return b"\0asm\x01\0\0\0" + b"\0" + bytes([len(payload)]) + payload


class CheckRelease(unittest.TestCase):
    def run_check(self, data, sha256=None):
        path, e = entry()
        rel = dict(e["releases"][0], url=URL, sha256=sha256 or hashlib.sha256(data).hexdigest())
        with mock.patch.object(registry, "download", return_value=data):
            return registry.check_release(path, e, rel, None)

    def assertFails(self, data, text, **kw):
        errors = self.run_check(data, **kw)
        self.assertTrue(any(text in err for err in errors), errors)

    def test_a_good_archive_passes(self):
        self.assertEqual(self.run_check(archive(good_files())), [])

    def test_a_wrong_sha256_fails(self):
        self.assertFails(archive(good_files()), "the entry says", sha256="0" * 64)

    def test_a_link_fails(self):
        self.assertFails(archive(good_files(), {"webhook-notifier/x": "/etc/passwd"}), "only plain files")

    def test_a_parent_path_fails(self):
        files = dict(good_files(), **{"webhook-notifier/../evil.lua": "x"})
        self.assertFails(archive(files), "inside one top folder")

    def test_a_file_outside_any_folder_fails(self):
        self.assertFails(archive(dict(good_files(), **{"loose.lua": "x"})), "inside one top folder")

    def test_two_top_folders_fail(self):
        self.assertFails(archive(dict(good_files(), **{"other/main.lua": "x"})), "exactly one top folder")

    def test_a_missing_manifest_fails(self):
        self.assertFails(archive({"webhook-notifier/main.lua": "x"}), "no plugin.toml")

    def test_a_missing_entry_file_fails(self):
        self.assertFails(archive({"webhook-notifier/plugin.toml": MANIFEST}), "main.lua is missing")

    def test_a_manifest_name_or_version_mismatch_fails(self):
        self.assertFails(archive(good_files(MANIFEST.replace('"webhook-notifier"', '"other"'))), "name is 'other'")
        self.assertFails(archive(good_files(MANIFEST.replace('"1.0.0"', '"1.0.1"'))), "version is '1.0.1'")

    def test_a_manifest_events_mismatch_fails(self):
        changed = MANIFEST.replace(', "download.failed"', "")
        self.assertFails(archive(good_files(changed)), "events differ")

    def test_a_manifest_hosts_mismatch_fails(self):
        changed = MANIFEST + 'hosts = ["example.com"]\n'
        self.assertFails(archive(good_files(changed)), "hosts.fixed")
        changed = MANIFEST.replace('["url"]', '["url", "other"]')
        self.assertFails(archive(good_files(changed)), "hosts.from_config")

    def test_a_manifest_without_its_links_fails(self):
        changed = MANIFEST.replace('license = "MIT"\n', "")
        self.assertFails(archive(good_files(changed)), "must set license")

    def test_a_failed_download_is_reported(self):
        path, e = entry()
        with mock.patch.object(registry, "download", side_effect=OSError("offline")):
            errors = registry.check_release(path, e, e["releases"][0], None)
        self.assertEqual(len(errors), 1)
        self.assertIn("download failed: offline", errors[0])


class Wasm(unittest.TestCase):
    def test_the_manifest_is_read_from_the_custom_section(self):
        self.assertEqual(registry.wasm_manifest(wasm_module('name = "x"\n')), 'name = "x"\n')

    def test_a_module_without_the_section_fails(self):
        with self.assertRaisesRegex(ValueError, "no putio-plugin section"):
            registry.wasm_manifest(b"\0asm\x01\0\0\0")

    def test_a_file_that_is_not_a_module_fails(self):
        with self.assertRaisesRegex(ValueError, "not a WebAssembly module"):
            registry.wasm_manifest(b"PK\3\4")


class CheckEntry(unittest.TestCase):
    def errors(self, **changes):
        path, e = entry()
        e.update(changes)
        return registry.check_entry(path, e)

    def test_the_example_entries_pass(self):
        for path in sorted((ROOT / "examples" / "entries").glob("*.toml")):
            with self.subTest(path.name):
                self.assertEqual(registry.check_entry(path, tomllib.loads(path.read_text())), [])

    def test_a_bundled_name_fails(self):
        path = Path("ntfy.toml")
        _, e = entry()
        self.assertIn("ntfy.toml: name: is a bundled plugin's name", registry.check_entry(path, dict(e, name="ntfy")))

    def test_the_name_must_match_the_file(self):
        self.assertTrue(any("must match the file name" in err for err in self.errors(name="other")))

    def test_links_must_be_https(self):
        self.assertTrue(any("docs:" in err for err in self.errors(docs="http://example.com")))

    def test_releases_must_be_newest_first(self):
        _, e = entry()
        old = dict(e["releases"][0], version="0.9.0")
        new = dict(e["releases"][0], version="1.0.0")
        self.assertFalse(any("newest first" in err for err in self.errors(releases=[new, old])))
        self.assertTrue(any("newest first" in err for err in self.errors(releases=[old, new])))

    def test_an_entry_needs_events_or_hooks(self):
        self.assertTrue(any("needs events, hooks or both" in err for err in self.errors(events=[])))
        self.assertFalse(any("needs events" in err for err in self.errors(events=[], hooks=["rename"])))

    def test_unknown_fields_fail(self):
        self.assertTrue(any("colour: unknown field" in err for err in self.errors(colour="red")))


class Pack(unittest.TestCase):
    def test_pack_makes_an_archive_the_check_accepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "webhook-notifier.tar.gz"
            args = mock.Mock(folder=str(ROOT / "examples" / "webhook-notifier"), out=str(out))
            with mock.patch("sys.stdout", io.StringIO()) as printed:
                registry.cmd_pack(args)
            data = out.read_bytes()
            self.assertEqual(printed.getvalue().strip(), hashlib.sha256(data).hexdigest())
            names = [n for n, _ in registry.members(data, URL)]
            self.assertIn("webhook-notifier/plugin.toml", names)
            self.assertTrue(all(n.startswith("webhook-notifier/") for n in names))


if __name__ == "__main__":
    unittest.main()
