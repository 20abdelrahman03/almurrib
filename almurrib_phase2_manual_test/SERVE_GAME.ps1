# Station 7 fallback static server - needs NOTHING except Windows itself.
# Serves this folder on 127.0.0.1 only (loopback, no admin rights needed).
# ASCII-only on purpose (codepage-safe). STATION7_NOBROWSER=1 skips the
# browser launch (automated testing hook).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8123
$mime = @{
  ".html" = "text/html; charset=utf-8"
  ".css" = "text/css; charset=utf-8"
  ".js" = "application/javascript; charset=utf-8"
  ".json" = "application/json; charset=utf-8"
  ".png" = "image/png"
  ".txt" = "text/plain; charset=utf-8"
}
$listener = New-Object Net.HttpListener
$listener.Prefixes.Add("http://127.0.0.1:$port/")
try {
  $listener.Start()
} catch {
  Write-Host "Cannot bind 127.0.0.1:$port : $_"
  Write-Host "Close the program using the port, then retry."
  pause
  exit 1
}
Write-Host "Serving $root"
Write-Host "Game: http://127.0.0.1:$port/browser/  (close this window to stop)"
if (-not $env:STATION7_NOBROWSER) {
  Start-Process "http://127.0.0.1:$port/browser/"
}
try {
  while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart("/")) -replace "/", "\"
    $full = [IO.Path]::GetFullPath((Join-Path $root $rel))
    if ((Test-Path $full -PathType Container)) { $full = Join-Path $full "index.html" }
    if (-not $full.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path $full -PathType Leaf)) {
      $ctx.Response.StatusCode = 404
      $buf = [Text.Encoding]::UTF8.GetBytes("not found")
      $ctx.Response.ContentLength64 = $buf.Length
      $ctx.Response.OutputStream.Write($buf, 0, $buf.Length)
      $ctx.Response.Close()
      continue
    }
    $ext = [IO.Path]::GetExtension($full).ToLower()
    $ctx.Response.ContentType = $(if ($mime.ContainsKey($ext)) { $mime[$ext] } else { "application/octet-stream" })
    $bytes = [IO.File]::ReadAllBytes($full)
    $ctx.Response.ContentLength64 = $bytes.Length
    $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $ctx.Response.Close()
  }
} finally {
  $listener.Stop()
}
