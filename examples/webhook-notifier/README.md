# webhook-notifier

Sends a POST with a small JSON body to a webhook when a download finishes or fails.

## Settings

| Setting | What it is |
|---------|------------|
| **Webhook URL** (secret) | Where to send the message |
| **Send the file's path** | Off (default) sends the file name only |

## What it sends, and where

Only to the host of **Webhook URL**:

```json
{ "event": "download.finished", "time": "2026-11-04T09:12:33.120Z",
  "name": "episode.mkv", "size_bytes": 734003200 }
```

A failed download sends `reason` instead of `size_bytes`. With **Send the file's path** on, `path`
holds the path under the download folder. Nothing else is sent.

## Events

`download.finished` and `download.failed`. **Send test event** sends `plugin.test`, which posts a
message with `"event": "plugin.test"` and no file fields.
