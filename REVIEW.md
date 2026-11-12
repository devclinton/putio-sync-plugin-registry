# Review checklist

A maintainer checks each new entry and each new release against this list before merging. CI
checks the items marked **(CI)**; the rest are read by a person.

## The entry

- [ ] **(CI)** The entry file is `plugins/<name>.toml` and its `name` matches.
- [ ] **(CI)** The name is not used by another entry or by a bundled plugin (`ntfy`, `discord`,
      `telegram`, `pushover`, `plex`, `jellyfin`, `emby`).
- [ ] **(CI)** Every release archive downloads over `https` and matches its `sha256`.
- [ ] **(CI)** The archive holds exactly one top folder with `plugin.toml` and the entry file,
      no links, no paths outside the folder, at most 200 files and 5 MB unpacked.
- [ ] **(CI)** The archive's `plugin.toml` has the entry's `name`, `version`, `events` and hosts,
      and passes `putio-sync plugins check`.
- [ ] The description says what the plugin does in one sentence.

## The manifest

- [ ] `author`, `repository` and `license` are set. The license is an open source license (an
      OSI-approved SPDX identifier).
- [ ] `docs` or `homepage` points to a page that explains the settings.
- [ ] Every setting that holds a token, key or password has `secret = true`.
- [ ] `[permissions.http]` names the fewest hosts needed. Prefer `host_from_config` over a fixed
      list when the user picks the server.
- [ ] `store = true` only when the plugin keeps values between calls.
- [ ] It subscribes to the events it uses, not `["*"]`, unless it really handles every event.

## The code

- [ ] It sends only the data its README says it sends, only to the hosts it names.
- [ ] It never logs secrets, tokens or whole request bodies that may hold them.
- [ ] It does not `load` text from the network or the store and run it.
- [ ] It handles `nil, err` from `putio.http.request` and non-2xx statuses, and raises an error
      with a clear message when it fails.
- [ ] Repeated events are grouped or rate-limited when the service it calls has limits.
- [ ] `health()` is defined if the plugin talks to a server the user configures.

## The plugin's repository

- [ ] It has a README with what the plugin does, its settings, the hosts it contacts and the data
      it sends.
- [ ] The release is tagged with the manifest's version and has release notes.
- [ ] Problems can be reported (issues are open, or `issues` points elsewhere).

## A new release

- [ ] The version is higher than the last listed one.
- [ ] New hosts, settings or events are named in the release notes.
- [ ] The code diff since the last listed release was read.
