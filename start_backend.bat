@echo off
echo ==============================
echo  KellyCopilot Backend Setup
echo ==============================
echo.

cd backend

REM Check for API key
if "%ANTHROPIC_API_KEY%"=="" (
    echo WARNING: ANTHROPIC_API_KEY is not set!
    echo.
    set /p KEY="Enter your Anthropic API key: "
    set ANTHROPIC_API_KEY=%KEY%
)

echo Installing dependencies...
pip install -r requirements.txt --upgrade -q

echo.
echo Starting backend on http://localhost:8000 ...
echo API docs: http://localhost:8000/docs
echo.
uvicorn main:app --reload --port 8000 --host 0.0.0.0
