# Adding a plugin to the registry

Thanks for writing a plugin. This page walks through listing one, using
[`examples/webhook-notifier`](examples/webhook-notifier) as the example. Read
[PLUGINS.md](https://github.com/devclinton/putio-sync/blob/main/PLUGINS.md) first for how plugins
work, and [EVENTS.md](https://github.com/devclinton/putio-sync/blob/main/EVENTS.md) for the events.

A maintainer reviews every pull request against the [review checklist](REVIEW.md) and merges it
when it passes. Please read the checklist before you start; most review comments come from it.

## 1. Keep the plugin in its own repository

The registry lists plugins; it does not hold their code. Make a public repository with the plugin
folder at its root or in a subfolder:

```
putio-sync-webhook-notifier/
  plugin.toml
  main.lua
  README.md
  LICENSE
```

The plugin must be one self-contained folder. The helper files bundled plugins share
(`notifier.lua`, `mediaserver.lua`) are not available to it.

## 2. Fill in the manifest's links

Besides the usual fields, set who made the plugin and where to read more. putio-sync shows these
on the plugin's tab:

```toml
name = "webhook-notifier"
version = "1.0.0"
description = "POST a small JSON message to a webhook when a download finishes or fails"
events = ["download.finished", "download.failed"]

author = "your-github-login"                       # required for the registry
license = "MIT"                                    # required; SPDX, OSI-approved
repository = "https://github.com/you/putio-sync-webhook-notifier"   # required
docs = "https://github.com/you/putio-sync-webhook-notifier#readme"  # recommended
homepage = "https://example.com/webhook-notifier"  # optional
issues = "https://github.com/you/putio-sync-webhook-notifier/issues"   # optional
```

Links must be `https`. The README should say what the plugin sends, to which hosts, and what each
setting does; [the example's README](examples/webhook-notifier/README.md) shows the shape.

## 3. Check it

```bash
putio-sync plugins check ./putio-sync-webhook-notifier
```

It checks the manifest and the Lua the same way **Reload plugins** does and prints each problem.
Then try it for real: copy the folder into your plugins folder, **Reload plugins**, enable it, and
use **Send test event**.

## 4. Tag a release with an archive

The archive holds one top folder with the plugin's files, and nothing else. Use `.tar.gz`. A
WebAssembly plugin can instead release its `.wasm` module, with its `plugin.toml` in the
module's `putio-plugin` section (see
[WebAssembly plugins](https://github.com/devclinton/putio-sync/blob/main/PLUGINS.md#webassembly-plugins)).
With a copy of this repository:

```bash
python3 scripts/registry.py pack ./putio-sync-webhook-notifier webhook-notifier-1.0.0.tar.gz
```

That prints the archive's SHA-256. Without it (macOS `tar`; on Linux use
`--transform 's/^putio-sync-webhook-notifier/webhook-notifier/'` instead of `-s`):

```bash
tar -czf webhook-notifier-1.0.0.tar.gz --exclude '.*' -s '/^putio-sync-webhook-notifier/webhook-notifier/' putio-sync-webhook-notifier
shasum -a 256 webhook-notifier-1.0.0.tar.gz
```

Tag the version (`v1.0.0`), create a GitHub release with notes, and attach the archive. Do not
replace a release's archive later: its SHA-256 is pinned, and installs will refuse the new file.
Publish a new version instead.

## 5. Add the entry

Fork this repository, copy [`templates/entry.toml`](templates/entry.toml) to
`plugins/webhook-notifier.toml`, and fill it in. [`examples/entries/`](examples/entries/) has
complete entries. The entry repeats the manifest's name, runtime, events, sync rules (`hooks`) and hosts so people can see what a
plugin does before they install it; CI checks that they match the archive.

Check it before you push:

```bash
python3 scripts/registry.py check plugins/webhook-notifier.toml
```

This downloads your archive, checks the SHA-256, the files in it, and the manifest against the
entry. Add `--putio-sync $(which putio-sync)` to run `putio-sync plugins check` on it too.

## 6. Open a pull request

Title it `Add webhook-notifier 1.0.0`. The pull request template asks you to tick the review
checklist. CI runs the same check as step 5. A maintainer reads the code, may ask questions, and
merges it. On merge, `index.json` is rebuilt and putio-sync shows the plugin under **More plugins**
the next time someone opens the Plugins page (or within 6 hours).

## New versions

Tag and release as in step 4, then open a pull request that adds a `[[releases]]` block at the
**top** of your entry (newest first; keep the old ones). Title it `webhook-notifier 1.1.0`. Name
any new hosts, settings or events in the release notes: putio-sync shows them to people before they
update, and new hosts need their approval again.

## Withdrawing a plugin

Open a pull request that sets `withdrawn = "reason"` in the entry, or ask in an issue. Installed
copies keep working and show the reason; the plugin is no longer offered for install.

## What is not accepted

- A bundled plugin's name (`ntfy`, `discord`, `telegram`, `pushover`, `plex`, `jellyfin`, `emby`),
  or a name close enough to one to confuse people.
- Plugins without an open source license, or whose code is not in a public repository.
- Plugins that send data their README does not mention, or contact hosts they do not need.
- Archives that are not one plugin folder, or that change after they are listed.
