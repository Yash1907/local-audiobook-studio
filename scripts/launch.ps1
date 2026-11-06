$ErrorActionPreference='Stop'
if (!(Test-Path frontend\dist\index.html)) { Push-Location frontend; npm run build; Pop-Location }
& .\.venv\Scripts\python.exe -m desktop.launcher
