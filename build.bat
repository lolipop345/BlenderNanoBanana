@echo off
setlocal enabledelayedexpansion

echo ================================================
echo  BlenderNanoBanana - Build + Install Script
echo ================================================
echo.

:: ── Config ────────────────────────────────────────────────────────────────────
set ADDON_SRC=blender_addon
set ADDON_NAME=nano_banana
set ZIP_OUT=nano_banana.zip

:: Find Blender addons folder automatically (checks common versions)
set BLENDER_ADDONS=
for %%V in (4.3 4.2 4.1 4.0 3.6 3.5) do (
    set CANDIDATE=%APPDATA%\Blender Foundation\Blender\%%V\scripts\addons
    if exist "!CANDIDATE!" (
        if "!BLENDER_ADDONS!"=="" (
            set BLENDER_ADDONS=!CANDIDATE!
            set BLENDER_VER=%%V
        )
    )
)

:: ── Menu ──────────────────────────────────────────────────────────────────────
echo  [1] Install for testing   (copy to Blender addons folder)
echo  [2] Build release zip     (nano_banana.zip)
echo  [3] Build Rust backend    (requires Rust / cargo)
echo  [4] All: Rust + zip
echo.
set /p CHOICE="Choose [1-4]: "

if "%CHOICE%"=="1" goto :install
if "%CHOICE%"=="2" goto :zip
if "%CHOICE%"=="3" goto :rust
if "%CHOICE%"=="4" goto :all
echo Invalid choice.
goto :end

:: ── Install for testing ────────────────────────────────────────────────────────
:install
if "%BLENDER_ADDONS%"=="" (
    echo [ERROR] Blender addons folder not found automatically.
    echo Please copy the '%ADDON_SRC%' folder manually to:
    echo   %%APPDATA%%\Blender Foundation\Blender\VERSION\scripts\addons\
    echo and rename it to '%ADDON_NAME%'
    goto :end
)

set TARGET=%BLENDER_ADDONS%\%ADDON_NAME%

echo.
echo Blender version found: %BLENDER_VER%
echo Target: %TARGET%
echo.

:: Remove old version
if exist "%TARGET%" (
    echo Removing old version...
    rmdir /s /q "%TARGET%"
)

:: Copy addon
echo Copying addon...
xcopy /e /i /q "%ADDON_SRC%" "%TARGET%"

:: Copy Rust binary if it exists
set RUST_BIN=rust_backend\target\release\nano_banana_backend.exe
if exist "%RUST_BIN%" (
    echo Copying Rust binary...
    copy /y "%RUST_BIN%" "%TARGET%\"
    echo [OK] Rust binary copied.
) else (
    echo [WARN] Rust binary not found at %RUST_BIN%
    echo        Run option [3] to build it, or the addon will work without it.
)

echo.
echo [DONE] Addon installed!
echo.
echo Next steps:
echo   1. Open Blender
echo   2. Edit ^> Preferences ^> Add-ons ^> search "Nano Banana"
echo   3. Enable it
echo   4. Check System Console for dependency install progress
echo.
goto :end

:: ── Build zip ─────────────────────────────────────────────────────────────────
:zip
echo.
echo Building %ZIP_OUT%...

:: Copy binary into addon source so it gets included in zip
set RUST_BIN=rust_backend\target\release\nano_banana_backend.exe
if exist "%RUST_BIN%" (
    copy /y "%RUST_BIN%" "%ADDON_SRC%\"
    echo [OK] Binary copied into addon folder for packaging.
) else (
    echo [WARN] Rust binary not found at %RUST_BIN%
    echo        The zip will be created without the Rust backend.
)

:: Delete old zip
if exist "%ZIP_OUT%" del "%ZIP_OUT%"

:: Use PowerShell to create zip with correct folder name inside
powershell -NoProfile -Command ^
    "$src = '%ADDON_SRC%'; $dst = '%ADDON_NAME%'; $zip = '%ZIP_OUT%';" ^
    "$tmp = [System.IO.Path]::Combine($env:TEMP, 'nb_build'); " ^
    "if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }; " ^
    "New-Item -ItemType Directory -Path $tmp | Out-Null; " ^
    "Copy-Item $src -Destination \"$tmp\$dst\" -Recurse; " ^
    "Compress-Archive -Path \"$tmp\$dst\" -DestinationPath $zip -Force; " ^
    "Remove-Item $tmp -Recurse -Force; " ^
    "Write-Host '[DONE] Created: ' -NoNewline; Write-Host $zip"

if exist "%ZIP_OUT%" (
    echo.
    echo Install from zip:
    echo   Blender ^> Edit ^> Preferences ^> Add-ons ^> Install ^> select %ZIP_OUT%
) else (
    echo [ERROR] Zip creation failed.
)
goto :end

:: ── Build Rust ────────────────────────────────────────────────────────────────
:rust
echo.
echo Building Rust backend...

where cargo >nul 2>&1
if not errorlevel 1 goto :cargo_found

echo [WARN] Cargo not found.
set /p INSTALL_RUST="Download and install Rust/Cargo? (Y/N): "
if /I not "!INSTALL_RUST!"=="Y" (
    echo [ERROR] Rust installation aborted.
    exit /b 1
)

echo Downloading Rust installer...
powershell -Command "Invoke-WebRequest -Uri 'https://win.rustup.rs/x86_64' -OutFile 'rustup-init.exe'"
if not exist rustup-init.exe (
    echo [ERROR] Download failed. Install manually from https://rustup.rs/
    exit /b 1
)

echo Installing Rust...
rustup-init.exe -y --quiet
if errorlevel 1 (
    echo [ERROR] Rust installation failed. Please check your internet connection.
    del rustup-init.exe
    exit /b 1
)

echo Setting PATH temporarily...
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
del rustup-init.exe
echo Rust installed successfully.

:cargo_found
cd rust_backend
:: Ensure rustup knows a default (fixes missing toolchain errors)
rustup default stable >nul 2>&1

:: Check if MSVC linker is installed. If not, fallback to GNU toolchain natively.
where link >nul 2>&1
if not errorlevel 1 goto :build_msvc

echo [INFO] Microsoft Visual C++ Build Tools not found (link.exe missing).
echo [INFO] Switching to GNU toolchain to avoid massive Visual Studio download...
rustup toolchain install stable-x86_64-pc-windows-gnu
cargo +stable-x86_64-pc-windows-gnu build --release
goto :check_build

:build_msvc
cargo build --release

:check_build
if errorlevel 1 (
    echo [ERROR] Rust build failed. Check errors above.
    cd ..
    exit /b 1
)
cd ..
echo.
echo [DONE] Rust binary: rust_backend\target\release\nano_banana_backend.exe
exit /b 0

:: ── All ───────────────────────────────────────────────────────────────────────
:all
call :rust
if errorlevel 1 goto :end

goto :zip

:end
echo.
pause
