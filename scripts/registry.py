#!/usr/bin/env python3
"""Check registry entries and build index.json.

    registry.py check [--offline] [--putio-sync PATH] [ENTRY ...]
    registry.py build
    registry.py pack FOLDER OUT.tar.gz

`check` validates every entry under plugins/ (or the ones given). Without --offline it also
downloads each release (a .tar.gz/.tgz archive, or a .wasm module carrying its manifest),
compares its SHA-256, inspects its contents, and compares its plugin.toml with the entry. With --putio-sync it runs `putio-sync plugins check` on the
unpacked folder. `build` writes index.json from the entries. `pack` makes a release archive
the way CONTRIBUTING.md describes, and prints its SHA-256.

Standard library only (Python 3.11+).
"""

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "plugins"
INDEX = ROOT / "index.json"

BUNDLED = {"ntfy", "discord", "telegram", "pushover", "plex", "jellyfin", "emby"}
NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")
SPDX = re.compile(r"^[A-Za-z0-9.+() -]{1,60}$")
MAX_ARCHIVE = 5 * 1024 * 1024
MAX_UNPACKED = 5 * 1024 * 1024
MAX_FILES = 200

REQUIRED = {"name", "description", "author", "repository", "license", "releases"}
OPTIONAL = {"docs", "homepage", "issues", "hosts", "withdrawn", "runtime", "events", "hooks"}
HOOKS = {"filter", "rename", "folder"}
WASM_SECTION = b"putio-plugin"
RELEASE_REQUIRED = {"version", "url", "sha256", "min_putio_sync"}
RELEASE_OPTIONAL = {"notes"}


def https(value):
    return isinstance(value, str) and value.startswith("https://") and len(value) <= 300


def version_key(v):
    return tuple(int(p) for p in re.match(r"^(\d+)\.(\d+)\.(\d+)", v).groups())


def check_entry(path, entry):
    """Errors in one entry's own fields, as 'file: field: message'."""
    errors = []

    def err(field, msg):
        errors.append(f"{path.name}: {field}: {msg}")

    for key in REQUIRED - entry.keys():
        err(key, "missing")
    for key in entry.keys() - REQUIRED - OPTIONAL:
        err(key, "unknown field")

    name = entry.get("name", "")
    if not NAME.match(name):
        err("name", "letters, digits, - and _ only; up to 40")
    elif path.stem != name:
        err("name", f"must match the file name ({path.stem})")
    if name in BUNDLED:
        err("name", "is a bundled plugin's name")
    if not 1 <= len(entry.get("description", "")) <= 300:
        err("description", "1 to 300 characters")
    if not 1 <= len(entry.get("author", "")) <= 100:
        err("author", "1 to 100 characters")
    if not SPDX.match(entry.get("license", "")):
        err("license", "an SPDX identifier, such as MIT or Apache-2.0")
    for key in ("repository", "docs", "homepage", "issues"):
        if key in entry and not https(entry[key]):
            err(key, "an https address, up to 300 characters")
    if entry.get("runtime", "lua") not in ("lua", "wasm"):
        err("runtime", "lua or wasm")
    events = entry.get("events", [])
    hooks = entry.get("hooks", [])
    if not isinstance(events, list) or not all(isinstance(e, str) for e in events):
        err("events", "a list of event types")
    if not isinstance(hooks, list) or set(hooks) - HOOKS:
        err("hooks", "a list of filter, rename and folder")
    if not events and not hooks:
        err("events", "an entry needs events, hooks or both")

    if "withdrawn" in entry and not 1 <= len(str(entry["withdrawn"])) <= 300:
        err("withdrawn", "a reason, 1 to 300 characters")

    hosts = entry.get("hosts", {})
    if not isinstance(hosts, dict) or hosts.keys() - {"fixed", "from_config"}:
        err("hosts", "only fixed and from_config")

    releases = entry.get("releases", [])
    if not releases:
        err("releases", "at least one")
    seen = []
    for i, rel in enumerate(releases):
        where = f"releases[{i}]"
        for key in RELEASE_REQUIRED - rel.keys():
            err(where, f"{key} missing")
        for key in rel.keys() - RELEASE_REQUIRED - RELEASE_OPTIONAL:
            err(where, f"{key}: unknown field")
        if not VERSION.match(rel.get("version", "")):
            err(where, "version must look like 1.2.3")
            continue
        if not VERSION.match(rel.get("min_putio_sync", "")):
            err(where, "min_putio_sync must look like 0.3.0")
        if not https(rel.get("url")):
            err(where, "url must be an https address")
        elif not rel["url"].endswith((".tar.gz", ".tgz", ".wasm")):
            err(where, "url must end in .tar.gz, .tgz or .wasm")
        if not SHA256.match(rel.get("sha256", "")):
            err(where, "sha256 must be 64 lowercase hex characters")
        if "notes" in rel and not https(rel["notes"]):
            err(where, "notes must be an https address")
        seen.append(rel["version"])
    if seen != sorted(seen, key=version_key, reverse=True) or len(set(seen)) != len(seen):
        err("releases", "newest first, each version once")
    return errors


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "putio-sync-plugin-registry"})
    with urllib.request.urlopen(req, timeout=60) as r:
        if not r.geturl().startswith("https://"):
            raise ValueError("redirected to a non-https address")
        data = r.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise ValueError("archive is larger than 5 MB")
    return data


def leb(data, pos):
    value = shift = 0
    while True:
        if pos >= len(data):
            raise ValueError("truncated module")
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return value, pos


def wasm_manifest(data):
    """The text of a module's putio-plugin custom section, as putio-sync reads it."""
    if data[:4] != b"\0asm":
        raise ValueError("not a WebAssembly module")
    pos = 8
    while pos < len(data):
        section = data[pos]
        size, pos = leb(data, pos + 1)
        end = pos + size
        if section == 0:
            length, at = leb(data, pos)
            if data[at:at + length] == WASM_SECTION:
                return data[at + length:end].decode()
        pos = end
    raise ValueError("the module has no putio-plugin section with its manifest")


def members(data, url):
    """(path, bytes) for each file; refuses links, absolute paths and '..'."""
    files = []
    if url.endswith(".wasm"):
        manifest = wasm_manifest(data)
        return [("plugin/plugin.toml", manifest.encode()), ("plugin/plugin.wasm", data)]
    if url.endswith((".tar.gz", ".tgz")):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
            for m in t.getmembers():
                if m.isdir():
                    continue
                if not m.isfile():
                    raise ValueError(f"{m.name}: only plain files are allowed")
                files.append((m.name, t.extractfile(m).read()))
    else:
        raise ValueError("url must end in .tar.gz, .tgz or .wasm")

    if len(files) > MAX_FILES:
        raise ValueError(f"more than {MAX_FILES} files")
    if sum(len(b) for _, b in files) > MAX_UNPACKED:
        raise ValueError("more than 5 MB unpacked")
    tops = set()
    for name, _ in files:
        parts = Path(name).parts
        if name.startswith("/") or ".." in parts or len(parts) < 2:
            raise ValueError(f"{name}: every file must be inside one top folder")
        tops.add(parts[0])
    if len(tops) != 1:
        raise ValueError("the archive must hold exactly one top folder")
    return files


def check_release(path, entry, rel, putio_sync):
    where = f"{path.name}: releases[{rel['version']}]"
    try:
        data = download(rel["url"])
    except Exception as e:  # noqa: BLE001 - report any download failure
        return [f"{where}: download failed: {e}"]
    digest = hashlib.sha256(data).hexdigest()
    if digest != rel["sha256"]:
        return [f"{where}: sha256 is {digest}, the entry says {rel['sha256']}"]
    try:
        files = dict((Path(n).relative_to(Path(n).parts[0]).as_posix(), b) for n, b in members(data, rel["url"]))
    except ValueError as e:
        return [f"{where}: {e}"]
    if "plugin.toml" not in files:
        return [f"{where}: no plugin.toml in the top folder"]
    try:
        manifest = tomllib.loads(files["plugin.toml"].decode())
    except Exception as e:  # noqa: BLE001
        return [f"{where}: plugin.toml: {e}"]

    errors = []
    default = "plugin.wasm" if manifest.get("runtime") == "wasm" else "main.lua"
    entry_file = manifest.get("entry") or default
    if entry_file not in files:
        errors.append(f"{where}: {entry_file} is missing")
    if manifest.get("runtime", "lua") != entry.get("runtime", "lua"):
        errors.append(f"{where}: plugin.toml runtime differs from the entry's")
    for key in ("name", "version"):
        want = entry["name"] if key == "name" else rel["version"]
        if manifest.get(key) != want:
            errors.append(f"{where}: plugin.toml {key} is {manifest.get(key)!r}, the entry says {want!r}")
    for key in ("events", "hooks"):
        if sorted(manifest.get(key, [])) != sorted(entry.get(key, [])):
            errors.append(f"{where}: plugin.toml {key} differ from the entry's")
    http = manifest.get("permissions", {}).get("http", {})
    hosts = entry.get("hosts", {})
    if sorted(http.get("hosts", [])) != sorted(hosts.get("fixed", [])):
        errors.append(f"{where}: plugin.toml hosts differ from the entry's hosts.fixed")
    if sorted(http.get("host_from_config", [])) != sorted(hosts.get("from_config", [])):
        errors.append(f"{where}: plugin.toml host_from_config differs from the entry's hosts.from_config")
    for key in ("author", "repository", "license"):
        if not manifest.get(key):
            errors.append(f"{where}: plugin.toml must set {key}")

    if putio_sync and not errors:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / entry["name"]
            for rel_path, body in files.items():
                target = folder / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
            run = subprocess.run([putio_sync, "plugins", "check", str(folder)], capture_output=True, text=True)
            if run.returncode != 0:
                errors.append(f"{where}: putio-sync plugins check:\n{run.stdout}{run.stderr}")
    return errors


def load(paths):
    entries = []
    for path in paths:
        try:
            entries.append((path, tomllib.loads(path.read_text())))
        except tomllib.TOMLDecodeError as e:
            entries.append((path, e))
    return entries


def cmd_check(args):
    listed = sorted(ENTRIES.glob("*.toml"))
    targets = [Path(p).resolve() for p in args.entries] or listed
    errors = []
    names = {}
    for path, entry in load(sorted(set(listed) | set(targets))):
        if isinstance(entry, Exception):
            errors.append(f"{path.name}: {entry}")
            continue
        names.setdefault(entry.get("name", "").lower(), []).append(path.name)
        if path not in targets:
            continue
        own = check_entry(path, entry)
        errors += own
        if own or args.offline:
            continue
        for rel in entry["releases"]:
            errors += check_release(path, entry, rel, args.putio_sync)
    for name, files in names.items():
        if len(files) > 1:
            errors.append(f"{', '.join(files)}: name {name!r} is used more than once")
    for e in errors:
        print(e, file=sys.stderr)
    print(f"{len(targets)} entries checked, {len(errors)} problems")
    return 1 if errors else 0


def cmd_build(_args):
    plugins = []
    for path, entry in load(sorted(ENTRIES.glob("*.toml"))):
        if isinstance(entry, Exception) or check_entry(path, entry):
            print(f"{path.name}: invalid, run check", file=sys.stderr)
            return 1
        plugins.append(entry)
    index = {"schema_version": 1, "plugins": plugins}
    INDEX.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    print(f"index.json: {len(plugins)} plugins")
    return 0


def cmd_pack(args):
    folder = Path(args.folder).resolve()
    manifest = tomllib.loads((folder / "plugin.toml").read_text())
    with tarfile.open(args.out, "w:gz") as t:
        for f in sorted(folder.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                t.add(f, arcname=f"{manifest['name']}/{f.relative_to(folder).as_posix()}")
    print(hashlib.sha256(Path(args.out).read_bytes()).hexdigest())
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("entries", nargs="*")
    c.add_argument("--offline", action="store_true", help="skip downloads")
    c.add_argument("--putio-sync", help="path to a putio-sync binary with `plugins check`")
    c.set_defaults(func=cmd_check)
    sub.add_parser("build").set_defaults(func=cmd_build)
    k = sub.add_parser("pack")
    k.add_argument("folder")
    k.add_argument("out")
    k.set_defaults(func=cmd_pack)
    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
