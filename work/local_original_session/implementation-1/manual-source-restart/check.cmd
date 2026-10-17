@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /Iwork\local_original_session\implementation-1\manual-source-restart\snapshot /Iwork\local_original_session\implementation-1\manual-source-restart /Iwork\local_original_session\implementation-1\manual-source-restart\snapshot\tools\local_native_login_state5_ack_bridge /sourceDependencies work\local_original_session\implementation-1\manual-source-restart\fixture-includes.json /Fe:work\local_original_session\implementation-1\manual-source-restart\command_mock.exe /Fo:work\local_original_session\implementation-1\manual-source-restart\command_mock.obj work\local_original_session\implementation-1\manual-source-restart\restart_mock.cpp work\local_original_session\implementation-1\manual-source-restart\guard.obj user32.lib
if errorlevel 1 exit /b 3
if "%1"=="mock-only" goto run
if "%1"=="cleanup-only" goto run
cl /nologo /c /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /Iwork\local_original_session\implementation-1\manual-source-restart\snapshot /Iwork\local_original_session\implementation-1\manual-source-restart /Iwork\local_original_session\implementation-1\manual-source-restart\snapshot\tools\local_native_login_state5_ack_bridge /sourceDependencies work\local_original_session\implementation-1\manual-source-restart\key-includes.json /Fo:work\local_original_session\implementation-1\manual-source-restart\key_compile.obj work\local_original_session\implementation-1\manual-source-restart\key_compile.cpp
if errorlevel 1 exit /b 4
:run
work\local_original_session\implementation-1\manual-source-restart\command_mock.exe %1
exit /b %errorlevel%





