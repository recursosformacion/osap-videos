# Resumen: empaqueta la app y el módulo ai-recogeYouTube, los sube a /opt/osap-videos
# y reinicia osap-videos.service. No toca config.yaml, .env, MySQL ni nginx.
# Uso: pwsh deploy/update.ps1 [-HostAlias RemoteIA]
param(
    [string]$HostAlias = "RemoteIA"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$module = Join-Path (Split-Path -Parent $root) "ai_recogeYouTube\src"
if (-not (Test-Path -LiteralPath $module)) {
    throw "No se encuentra el módulo en $module"
}

$stage = Join-Path $env:TEMP "osap-videos-stage"
$tar = Join-Path $env:TEMP "osap-videos.tar.gz"
Remove-Item -LiteralPath $stage, $tar -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($item in @("app.py", "schema.sql", "requirements.txt", "pyproject.toml", "README.md", "config.example.yaml", "templates", "static", "deploy")) {
    Copy-Item -LiteralPath (Join-Path $root $item) -Destination $stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $stage "vendor\ai_recogeYouTube") | Out-Null
Copy-Item -LiteralPath $module -Destination (Join-Path $stage "vendor\ai_recogeYouTube\src") -Recurse -Force

tar -czf $tar -C $stage .
if ($LASTEXITCODE -ne 0) { throw "tar falló" }

ssh -o BatchMode=yes $HostAlias "mkdir -p ~/deploy_tmp"
scp -o BatchMode=yes $tar "${HostAlias}:~/deploy_tmp/osap-videos.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "scp falló" }

ssh -o BatchMode=yes $HostAlias @"
set -e
tar -xzf ~/deploy_tmp/osap-videos.tar.gz -C /opt/osap-videos
/opt/osap-videos/.venv/bin/pip install --quiet -r /opt/osap-videos/requirements.txt
sudo -n systemctl restart osap-videos.service
sleep 2
sudo -n systemctl is-active osap-videos.service
curl -fsS http://127.0.0.1:8400/health
"@
if ($LASTEXITCODE -ne 0) { throw "despliegue o healthcheck falló" }

Write-Host "osap-videos actualizado y saludable."

