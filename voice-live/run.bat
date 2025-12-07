@echo off
echo ========================================
echo Azure VoiceLive Web Assistant
echo ========================================
echo.

REM Check if .env file exists
if not exist .env (
    echo WARNING: .env file not found!
    echo Please create a .env file with your API Details:
    echo AZURE_VOICELIVE_ENDPOINT=your-voicelive-endpoint
    echo AZURE_VOICELIVE_MODEL=voicelive-supported-model
    echo AZURE_VOICELIVE_API_KEY=your_api_key_here
    echo.
)

REM Check if virtual environment exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update requirements
echo Checking dependencies...
pip install -r requirements.txt --quiet
echo.

REM Run the application
echo Starting Flask application...
echo Web UI will be available at: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python app.py

pause
