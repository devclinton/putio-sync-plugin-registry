<!-- Title: "Add <name> <version>" for a new plugin, "<name> <version>" for a new release. -->

**Plugin:** <!-- name and version -->
**Repository:** <!-- link -->
**Release:** <!-- link to the release with the archive -->

What it does, in a sentence or two:

Hosts it contacts and why:

## Checklist

- [ ] I ran `python3 scripts/registry.py check plugins/<name>.toml` and it passed.
- [ ] I tried it in putio-sync with **Send test event**.
- [ ] The manifest sets `author`, `repository` and `license`, and its links work.
- [ ] Secrets are marked `secret = true`.
- [ ] The README says what it sends, to which hosts, and what each setting does.
- [ ] I read [REVIEW.md](../REVIEW.md); anything that does not apply is explained below.

<!-- For a new release: what changed, and any new hosts, settings or events. -->
