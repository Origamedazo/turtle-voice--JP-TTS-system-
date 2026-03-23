@echo off
echo ==============================================
echo turtle voice tts GUI - PyInstaller Build Script
echo ==============================================
echo.
echo Installing requirements...
pip install pyinstaller pyqtgraph sounddevice soundfile pandas numpy librosa PyQt6

echo.
echo Building executable from spec file...
pyinstaller --noconfirm "turtle_voice_GUI.spec"

echo.
echo Build complete. The executable is located in the "dist/turtle_voice_GUI" folder.
pause
