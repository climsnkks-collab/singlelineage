@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
pushd tools\local_original_session\native\vendor\detours\src
nmake /nologo DETOURS_TARGET_PROCESSOR=X64 "CFLAGS=/W4 /WX /Zi /MD /Gy /Gm- /Zl /O2 /DWIN32_LEAN_AND_MEAN /D_WIN32_WINNT=0x0601"
set guard_build_exit=%errorlevel%
popd
exit /b %guard_build_exit%
