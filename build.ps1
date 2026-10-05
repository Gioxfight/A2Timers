# Build dist\A2Timers-Setup-<version>.exe
# Requires: Python 3.12+, `pip install -r requirements-dev.txt`, Inno Setup 6.
# Native tools write progress to stderr: rely on exit codes, not on error records.
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
Set-Location $root

$version = (python -c "import version; print(version.__version__)").Trim()
Write-Host "== A2Timers $version"

Write-Host "== Tests"
python -m unittest discover -s tests -t .
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }

Write-Host "== Assets"
python tools/make_sounds.py
if ($LASTEXITCODE -ne 0) { throw "make_sounds failed" }
python tools/make_icon.py
if ($LASTEXITCODE -ne 0) { throw "make_icon failed" }

Write-Host "== PyInstaller"
python -m PyInstaller --noconfirm --clean --windowed --name A2Timers `
    --icon "$root\assets\icon.ico" `
    --add-data "$root\events.json;." `
    --add-data "$root\assets;assets" `
    --distpath "$root\build\dist" --workpath "$root\build\work" --specpath "$root\build" `
    "$root\A2Timers.pyw"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "== Inno Setup"
$iscc = @(
    (Get-Command iscc -ErrorAction SilentlyContinue).Source,
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)" }
& $iscc "/DAppVersion=$version" "$root\installer\A2Timers.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Write-Host "== Done: dist\A2Timers-Setup-$version.exe"
