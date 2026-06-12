param(
    [string]$OneBotWs = "ws://127.0.0.1:3001/",
    [long]$TargetGroup = 0,
    [long]$NotifyUser = 0,
    [string]$Config = "config.json",
    [string]$UrlPattern = "",
    [double]$ReconnectDelay = 5,
    [switch]$DryRun,
    [switch]$Headless,
    [switch]$Once,
    [switch]$NoNotify
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:UV_CACHE_DIR = Join-Path $env:TEMP "uv-cache-auto-form"

$listenerArgs = @(
    "run",
    "python",
    "main.py",
    "--listen-onebot",
    "--config",
    $Config,
    "--onebot-ws",
    $OneBotWs,
    "--reconnect-delay",
    [string]$ReconnectDelay
)

if ($TargetGroup -gt 0) {
    $listenerArgs += @("--target-group", [string]$TargetGroup)
}

if ($NotifyUser -gt 0) {
    $listenerArgs += @("--notify-user", [string]$NotifyUser)
}

if ($UrlPattern) {
    $listenerArgs += @("--url-pattern", $UrlPattern)
}

if ($DryRun) {
    $listenerArgs += "--dry-run"
}

if ($Headless) {
    $listenerArgs += "--headless"
}

if ($Once) {
    $listenerArgs += "--once"
}

if ($NoNotify) {
    $listenerArgs += "--no-notify"
}

& uv @listenerArgs
