$ErrorActionPreference='Stop'
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt pywebview pytest
Push-Location frontend
npm install
Pop-Location
