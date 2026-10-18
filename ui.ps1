$UiArgs = $args
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $taskRoot
$env:PYTHONNOUSERSITE = '1'
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = Join-Path $taskRoot '.tools\python\python.exe' }
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create .venv using the README first.' }
& $taskPython -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false @UiArgs
exit $LASTEXITCODE
