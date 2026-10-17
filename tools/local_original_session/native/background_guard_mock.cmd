@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
if not exist work\local_original_session\background-guard-compile mkdir work\local_original_session\background-guard-compile
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /Itools\local_original_session\native\vendor\detours\src tools\local_original_session\native\background_guard_mock.cpp tools\local_original_session\native\vendor\detours\lib.X64\detours.lib user32.lib /Fowork\local_original_session\background-guard-compile\background_guard_mock.obj /Fework\local_original_session\background-guard-compile\background_guard_mock.exe
exit /b %errorlevel%
