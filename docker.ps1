$DockerArgs = $args
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $taskRoot
$taskDocker = Get-Command docker.exe -ErrorAction SilentlyContinue
$taskCandidates = @(
    "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
    "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
)
if ($taskDocker) {
    $taskExecutable = $taskDocker.Source
} else {
    $taskExecutable = $taskCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $taskExecutable) { throw 'Docker CLI not found. Install and start Docker Desktop.' }
# Include the credential helper for this process only; no persistent PATH changes.
$env:PATH = "$(Split-Path -Parent $taskExecutable);$env:PATH"
& $taskExecutable @DockerArgs
exit $LASTEXITCODE
