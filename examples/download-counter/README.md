# download-counter

Counts finished downloads and their bytes per day (UTC) and, if a webhook is set, posts
yesterday's totals once a day. Shows how a plugin uses the store, `on_tick` and buttons.

## Settings and buttons

| | What it does |
|-|--------------|
| **Summary webhook** (secret, optional) | Receives one POST a day; empty means count only |
| **Show today's count** | Shows today's files and size |
| **Reset counts** | Forgets all stored totals |

## What it sends, and where

Only to the host of **Summary webhook**, once a day:

```json
{ "day": "2026-11-09", "files": 12, "bytes": 18253611008 }
```

No file names or paths are sent or stored.

## Store

One key per day still to be sent (`day:2026-11-10`) with `{files, bytes}`, and `sent` with the
last day sent. A day's key is deleted once it is sent.
