# Rebuild the PWA icons (192px and 512px PNG) from app\static\img\logo.svg.
# Uses Microsoft Edge in headless mode, which is on every Windows 10/11 PC.
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File scripts\make_icons.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$logo = Join-Path $root "app\static\img\logo.svg"
$outDir = Join-Path $root "app\static\img\icons"
New-Item -ItemType Directory -Force $outDir | Out-Null

$edge = @(
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw "Microsoft Edge not found." }

$svg = Get-Content $logo -Raw
$tmp = Join-Path $env:TEMP "dml-icon.html"

foreach ($size in 192, 512) {
  # Square dark-green background so the icon also works as a "maskable" icon;
  # the logo sits inside the 80% safe zone.
  $inner = [int]($size * 0.8)
  $html = @"
<!doctype html><html><head><style>
html,body{margin:0;width:${size}px;height:${size}px;background:#1d4a2c;overflow:hidden}
div{width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center}
svg{width:${inner}px;height:${inner}px}
</style></head><body><div>$svg</div></body></html>
"@
  Set-Content -Path $tmp -Value $html -Encoding utf8
  $out = Join-Path $outDir "icon-$size.png"
  $edgeArgs = @("--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
    "--window-size=$size,$size", "--screenshot=`"$out`"", "file:///$($tmp -replace '\\','/')")
  Start-Process -FilePath $edge -ArgumentList $edgeArgs -Wait -WindowStyle Hidden
  Write-Host "Wrote $out"
}
Remove-Item $tmp -ErrorAction SilentlyContinue
