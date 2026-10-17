@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /Iwork\local_original_session\implementation-1\manual-source-reselect /Iwork\local_original_session\implementation-1\manual-source-reselect\snapshot /Iwork\local_original_session\implementation-1\manual-source-restart /Iwork\local_original_session\implementation-1\manual-source-reselect /Iwork\local_original_session\implementation-1\manual-source-reselect\snapshot\tools\local_native_login_state5_ack_bridge /sourceDependencies work\local_original_session\implementation-1\source-use-ui-owned-callback\fixture-includes.json /Fe:work\local_original_session\implementation-1\source-use-ui-owned-callback\owned_ui_mock.exe /Fo:work\local_original_session\implementation-1\source-use-ui-owned-callback\owned_ui_mock.obj work\local_original_session\implementation-1\source-use-ui-owned-callback\owned_ui_mock.cpp work\local_original_session\implementation-1\source-use-ui-owned-callback\guard.obj user32.lib
if errorlevel 1 exit /b 3
work\local_original_session\implementation-1\source-use-ui-owned-callback\owned_ui_mock.exe %1
exit /b %errorlevel%
