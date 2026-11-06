$ErrorActionPreference='Stop'
if (!(Test-Path frontend\dist\index.html)) { Push-Location frontend; npm run build; Pop-Location }
Start-Process 'http://127.0.0.1:8765'
& .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765
