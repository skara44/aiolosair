@echo off
REM ----------------------------------------
REM Akıllı Asistan Sunucu Başlatma Scripti
REM ----------------------------------------

REM Sanal ortamı aktif et
call "%~dp0\venv\Scripts\activate.bat"

REM Sunucuyu başlat
echo Sunucu başlatılıyor...
uvicorn server:app --host 0.0.0.0 --port 8000 --reload


