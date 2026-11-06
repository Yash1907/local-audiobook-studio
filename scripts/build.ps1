$ErrorActionPreference='Stop'
Push-Location frontend
npm run build
Pop-Location
& .\.venv\Scripts\python.exe -m pip install pyinstaller
& .\.venv\Scripts\pyinstaller.exe --noconfirm --onedir --windowed --name LocalAudiobookStudio --paths (Get-Location).Path --add-data 'frontend\dist;frontend\dist' --collect-all kokoro_onnx desktop\launcher.py
