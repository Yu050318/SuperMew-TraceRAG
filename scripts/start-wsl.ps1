param([string]$Distribution = 'Ubuntu-24.04')

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& wsl.exe --distribution $Distribution --cd $projectRoot -- bash -lc 'export no_proxy="localhost,127.0.0.1,::1,${no_proxy:-}"; export NO_PROXY="$no_proxy"; export no_grpc_proxy="$no_proxy"; exec "$HOME/.local/share/supermew/venv/bin/python" -m backend.launcher --no-reload'
exit $LASTEXITCODE
