$CliArgs = $args
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $taskRoot
$env:PYTHONNOUSERSITE = '1'
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = Join-Path $taskRoot '.tools\python\python.exe'
}
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Create .venv using the README setup commands first.'
}
& $taskPython -m app.cli @CliArgs
exit $LASTEXITCODE
