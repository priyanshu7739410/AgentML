@echo off
echo Cleaning Python cache and build directories...

FOR /d /r . %%d IN (__pycache__) DO @IF EXIST "%%d" rd /s /q "%%d"
FOR /d /r . %%d IN (.pytest_cache) DO @IF EXIST "%%d" rd /s /q "%%d"
FOR /d /r . %%d IN (*.egg-info) DO @IF EXIST "%%d" rd /s /q "%%d"

if exist build rd /s /q build
if exist dist rd /s /q dist

echo Cleanup complete.
