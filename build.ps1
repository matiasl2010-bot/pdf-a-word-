Set-Location $PSScriptRoot
.\.venv\Scripts\pyinstaller.exe --onefile --windowed --name "PDF2Word" app.py
Write-Host "Build listo en dist\PDF2Word.exe"
