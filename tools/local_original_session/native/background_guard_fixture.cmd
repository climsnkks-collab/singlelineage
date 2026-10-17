@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
if not exist work\local_original_session\background-guard-compile mkdir work\local_original_session\background-guard-compile
cl /nologo /LD /DOWN_BACKGROUND_GUARD_FIXTURE_DLL /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /Itools\local_original_session\native\vendor\detours\src tools\local_original_session\native\background_guard_fixture.cpp tools\local_original_session\native\vendor\detours\lib.X64\detours.lib user32.lib /Fowork\local_original_session\background-guard-compile\background_guard_fixture_dll.obj /Fework\local_original_session\background-guard-compile\background_guard_fixture.dll /link /IMPLIB:work\local_original_session\background-guard-compile\background_guard_fixture.lib
if errorlevel 1 exit /b 3
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /Itools\local_original_session\native\vendor\detours\src tools\local_original_session\native\background_guard_fixture.cpp tools\local_original_session\native\vendor\detours\lib.X64\detours.lib user32.lib /Fowork\local_original_session\background-guard-compile\background_guard_fixture_host.obj /Fework\local_original_session\background-guard-compile\background_guard_fixture.exe
exit /b %errorlevel%
