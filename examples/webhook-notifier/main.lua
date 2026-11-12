-- POST one JSON message per finished or failed download to the configured webhook.
local plugin = {}

local function message(event)
  local d = event.data or {}
  local body = { event = event.type, time = event.occurred_at, name = d.name }
  if putio.config.include_path then
    body.path = d.relative_path
  end
  if event.type == "download.finished" then
    body.size_bytes = d.size_bytes
  elseif event.type == "download.failed" then
    body.reason = d.reason
  end
  return body
end

function plugin.on_event(event)
  local r, err = putio.http.request({
    method = "POST",
    url = putio.config.url,
    headers = { ["Content-Type"] = "application/json" },
    body = putio.json.encode(message(event)),
  })
  if not r then error(err) end
  if r.status >= 300 then error("webhook answered HTTP " .. r.status) end
end

return plugin
