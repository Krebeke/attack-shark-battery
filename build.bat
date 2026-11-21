@echo off
rem Збірка: dist\AttackSharkBattery\AttackSharkBattery.exe + (якщо встановлено Inno Setup) installer_output\AttackSharkBattery-Setup.exe
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  py -m venv .venv || goto :err
)
set PY=.venv\Scripts\python.exe

%PY% -m pip install -r requirements.txt pyinstaller || goto :err

rem --onedir: швидший старт, один процес, без розпакування у Temp
%PY% -m PyInstaller --noconsole --onedir --noconfirm --clean ^
  --name AttackSharkBattery ^
  --icon app.ico ^
  --version-file version_info.txt ^
  --hidden-import pystray._win32 ^
  --hidden-import hid ^
  --hidden-import ui ^
  --hidden-import PIL.ImageTk ^
  --exclude-module unittest --exclude-module pydoc --exclude-module doctest ^
  --exclude-module test --exclude-module distutils --exclude-module lib2to3 ^
  tray_battery.py || goto :err

copy /Y config.json dist\AttackSharkBattery\config.default.json >nul
echo.
echo [1/2] Готово: dist\AttackSharkBattery\AttackSharkBattery.exe

for /f %%v in ('%PY% -c "import version;print(version.VERSION)"') do set VER=%%v

set ISCC=
where iscc >nul 2>nul && set ISCC=iscc
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set ISCC="%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC (
  %ISCC% /DAppVer=%VER% installer.iss || goto :err
  echo [2/2] Готово: installer_output\AttackSharkBattery-Setup.exe
) else (
  echo [2/2] Inno Setup не знайдено - інсталятор не зібрано.
  echo       Встановіть з https://jrsoftware.org/isdl.php і запустіть build.bat ще раз.
)
goto :eof

:err
echo.
echo Помилка збірки.
exit /b 1
