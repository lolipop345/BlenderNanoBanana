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
for %%V in (5.1 5.0 4.4 4.3 4.2 4.1 4.0 3.6 3.5) do (
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
if "%CHOICE%"=="3" call :rust & goto :end
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

:: Resolve absolute paths so directory changes don't break anything
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set RUST_BIN=%ROOT%\rust_backend\target\release\nano_banana_backend.exe
set ADDON_SRC_ABS=%ROOT%\%ADDON_SRC%
set ZIP_OUT_ABS=%ROOT%\%ZIP_OUT%

:: NOTE: Rust binary is intentionally NOT included in the addon zip.
:: It is distributed separately. Users install the addon zip via Blender,
:: then place nano_banana_backend.exe next to the addon folder manually,
:: or use option [1] (Install for testing) which copies it automatically.

:: Delete old zip
if exist "%ZIP_OUT_ABS%" del "%ZIP_OUT_ABS%"

:: Use PowerShell to create zip with correct internal folder name
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try {" ^
    "  $src = '%ADDON_SRC_ABS%';" ^
    "  $dst = '%ADDON_NAME%';" ^
    "  $zip = '%ZIP_OUT_ABS%';" ^
    "  $tmp = Join-Path $env:TEMP 'nb_build';" ^
    "  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force };" ^
    "  New-Item -ItemType Directory -Path $tmp | Out-Null;" ^
    "  Copy-Item $src -Destination (Join-Path $tmp $dst) -Recurse;" ^
    "  Compress-Archive -Path (Join-Path $tmp $dst) -DestinationPath $zip -Force;" ^
    "  Remove-Item $tmp -Recurse -Force;" ^
    "  Write-Host '[OK] Created: ' -NoNewline; Write-Host $zip;" ^
    "} catch { Write-Error $_; exit 1 }"

if exist "%ZIP_OUT_ABS%" (
    echo.
    echo [DONE] Zip ready: %ZIP_OUT_ABS%
    echo.
    echo Install from zip:
    echo   Blender ^> Edit ^> Preferences ^> Add-ons ^> Install ^> select %ZIP_OUT%
) else (
    echo [ERROR] Zip creation failed. Check PowerShell error above.
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
pushd "%~dp0rust_backend"
:: Ensure rustup knows a default (fixes missing toolchain errors)
rustup default stable >nul 2>&1

:: Check if MSVC linker is installed.
where link >nul 2>&1
if not errorlevel 1 goto :build_msvc

:: MSVC not found. Check if MinGW dlltool is available for GNU toolchain.
echo [INFO] Microsoft Visual C++ Build Tools not found (link.exe missing).
where dlltool >nul 2>&1
if not errorlevel 1 goto :build_gnu

:: Neither MSVC nor MinGW in PATH. Auto-setup everything.
echo [INFO] MinGW not in PATH — auto-setting up toolchain...

:: Step 1: Check if MSYS2 is installed somewhere but dlltool not yet there (needs pacman)
set MSYS2_ROOT=
for %%P in (C:\msys64 C:\msys2 C:\tools\msys64) do (
    if exist "%%P\usr\bin\pacman.exe" (
        if "!MSYS2_ROOT!"=="" set MSYS2_ROOT=%%P
    )
)

if not "!MSYS2_ROOT!"=="" (
    echo [INFO] MSYS2 found at !MSYS2_ROOT!
    if not exist "!MSYS2_ROOT!\mingw64\bin\dlltool.exe" (
        echo [INFO] Installing mingw-w64 toolchain via pacman...
        "!MSYS2_ROOT!\usr\bin\pacman.exe" -S --noconfirm mingw-w64-x86_64-gcc mingw-w64-x86_64-binutils
    )
    if exist "!MSYS2_ROOT!\mingw64\bin\dlltool.exe" (
        echo [OK] MinGW ready — adding to PATH.
        set PATH=!MSYS2_ROOT!\mingw64\bin;!PATH!
        goto :build_gnu
    )
)

:: Step 2: MSYS2 not installed — install it automatically via winget
echo [INFO] Installing MSYS2 via winget (this takes a minute)...
winget install -e --id MSYS2.MSYS2 --accept-package-agreements --accept-source-agreements >nul 2>&1

:: Find it after install
set MSYS2_ROOT=
for %%P in (C:\msys64 C:\msys2 C:\tools\msys64) do (
    if exist "%%P\usr\bin\pacman.exe" (
        if "!MSYS2_ROOT!"=="" set MSYS2_ROOT=%%P
    )
)

if "!MSYS2_ROOT!"=="" (
    echo [ERROR] MSYS2 install failed or not found. Cannot build Rust backend.
    popd
    exit /b 1
)

echo [INFO] Installing mingw-w64 toolchain via pacman...
"!MSYS2_ROOT!\usr\bin\pacman.exe" -S --noconfirm mingw-w64-x86_64-gcc mingw-w64-x86_64-binutils

if not exist "!MSYS2_ROOT!\mingw64\bin\dlltool.exe" (
    echo [ERROR] MinGW install failed. Cannot build Rust backend.
    popd
    exit /b 1
)

echo [OK] MinGW ready — adding to PATH.
set PATH=!MSYS2_ROOT!\mingw64\bin;!PATH!

:build_gnu
echo [INFO] Using GNU toolchain with rust-lld (no MinGW required)...
rustup toolchain install stable-x86_64-pc-windows-gnu >nul 2>&1
rustup component add llvm-tools-preview >nul 2>&1
cargo +stable-x86_64-pc-windows-gnu build --release
goto :check_build

:build_msvc
cargo build --release

:check_build
if errorlevel 1 (
    echo [ERROR] Rust build failed. Check errors above.
    popd
    exit /b 1
)
popd
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
