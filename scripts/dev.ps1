$ErrorActionPreference='Stop'
Start-Process -WindowStyle Hidden -FilePath (Resolve-Path '.\.venv\Scripts\python.exe') -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8765' -WorkingDirectory (Get-Location).Path
Push-Location frontend
npm run dev
Pop-Location
