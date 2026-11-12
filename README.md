# putio-sync plugin registry

A list of reviewed [plugins](https://github.com/devclinton/putio-sync/blob/main/PLUGINS.md) (Lua or WebAssembly)
for [putio-sync](https://github.com/devclinton/putio-sync). putio-sync reads this list and shows it
on Settings › Plugins under **More plugins**, where a plugin can be installed with one click.

The registry holds no plugin code. Each entry in [`plugins/`](plugins/) points to one plugin's own
repository and to pinned releases (a `.tar.gz` of the plugin folder, or a `.wasm` module), each with
its SHA-256. putio-sync downloads the release, checks the SHA-256 and the manifest against the entry,
and only then writes it into the plugins folder.

> The in-app list and install arrive with the putio-sync release after 0.2.2. Until then,
> install a listed plugin by unpacking its release archive into the plugins folder and pressing
> **Reload plugins**.

## What "reviewed" means

A maintainer read the plugin's manifest, code and README against the
[review checklist](REVIEW.md) before merging its entry, and again for each new release.

It does **not** mean the plugin is guaranteed safe or bug-free. Every plugin, from here or
anywhere else, runs in the same putio-sync sandbox: it cannot read files, run programs or open
sockets, and it can only call hosts you approve when you turn it on. A new release that adds a host
asks for approval again.

## Using it

- The registry is on by default. Turn it off, or point putio-sync at another copy of
  `index.json`, in Settings › Plugins or in `config.toml`.
- putio-sync fetches the list only when **More plugins** is opened (at most every 6 hours) or
  **Refresh** is pressed.
- Installed plugins are off until you press **Enable**. Updates are offered, never installed on
  their own, and keep the plugin's settings. A release that adds a host needs your approval again.

## Adding a plugin

Read [CONTRIBUTING.md](CONTRIBUTING.md). In short: keep your plugin in its own repository, tag a
release with an archive of the plugin folder, add `plugins/<name>.toml` from the
[entry template](templates/entry.toml) and open a pull request. [`examples/`](examples/) has two
complete plugins and their entries to copy from.

## Layout

| Path | What it is |
|------|------------|
| `plugins/<name>.toml` | One entry per plugin |
| `index.json` | Built from the entries on `main`; what putio-sync reads |
| `templates/entry.toml` | A blank entry to copy |
| `examples/` | Example plugins and their entries |
| `REVIEW.md` | The review checklist |
| `scripts/registry.py` | Checks entries and builds `index.json` (used by CI) |
| `tests/` | Tests for the script: `python3 -m unittest discover -s tests` |

## License

The registry files are MIT licensed. Each plugin has its own license, given in its entry.
