-- Count finished downloads per UTC day in the store; post yesterday's totals once a day.
local plugin = {}

local function day(seconds)
  return string.sub(putio.time.iso(seconds), 1, 10)
end

local function totals(d)
  return putio.store.get("day:" .. d) or { files = 0, bytes = 0 }
end

function plugin.on_event(event)
  local d = day()
  local t = totals(d)
  t.files = t.files + 1
  t.bytes = t.bytes + (event.data.size_bytes or 0)
  local ok, err = putio.store.set("day:" .. d, t)
  if not ok then error(err) end
  putio.metrics.count("downloads")
end

-- Send yesterday's totals once, then drop its key so the store stays small.
function plugin.on_tick()
  local yesterday = day(putio.time.now() - 86400)
  if putio.store.get("sent") == yesterday then return end
  local t = totals(yesterday)
  local url = putio.config.summary_url
  if url and url ~= "" then
    local r, err = putio.http.request({
      method = "POST",
      url = url,
      headers = { ["Content-Type"] = "application/json" },
      body = putio.json.encode({ day = yesterday, files = t.files, bytes = t.bytes }),
    })
    if not r then error(err) end
    if r.status >= 300 then error("summary webhook answered HTTP " .. r.status) end
  end
  putio.store.set("sent", yesterday)
  putio.store.delete("day:" .. yesterday)
end

function plugin.on_action(id)
  if id == "reset" then
    for _, key in ipairs(putio.store.keys()) do
      putio.store.delete(key)
    end
    return { message = "Counts reset", done = true }
  end
  local t = totals(day())
  return {
    message = string.format("Today: %d files, %.1f GB", t.files, t.bytes / 1e9),
    done = true,
  }
end

return plugin
