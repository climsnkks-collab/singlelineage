@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
ml64 /nologo /c /Fowork\local_original_session\implementation-1\manual-source-restart\guard.obj work\local_original_session\implementation-1\manual-source-restart\snapshot\tools\local_native_login_state5_ack_bridge\guard_template.asm
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /LD /sourceDependencies work\local_original_session\implementation-1\manual-source-restart\build-includes.json /Iwork\local_original_session\implementation-1\manual-source-restart\snapshot /Iwork\local_original_session\implementation-1\manual-source-restart /Iwork\local_original_session\implementation-1\manual-source-restart\snapshot\tools\local_native_login_state5_ack_bridge /Fe:work\local_original_session\implementation-1\manual-source-restart\own-login-bridge-dg49.dll /Fo:work\local_original_session\implementation-1\manual-source-restart\bridge.obj work\local_original_session\implementation-1\manual-source-restart\diagnostic.cpp work\local_original_session\implementation-1\manual-source-restart\guard.obj user32.lib /link /def:work\local_original_session\implementation-1\manual-source-restart\bridge.def /out:work\local_original_session\implementation-1\manual-source-restart\own-login-bridge-dg49.dll /implib:work\local_original_session\implementation-1\manual-source-restart\own-login-bridge-dg49.lib /map:work\local_original_session\implementation-1\manual-source-restart\own-login-bridge-dg49.map
exit /b %errorlevel%




