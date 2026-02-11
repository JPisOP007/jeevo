@echo off
REM Quick setup script for Medical RAG System (Windows)
REM Run this to set up everything in one command

echo ====================================================================
echo MEDICAL RAG SYSTEM - QUICK SETUP (Windows)
echo ====================================================================

cd /d "%~dp0"

echo.
echo Step 1/3: Installing dependencies...
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install dependencies
    exit /b 1
)

echo.
echo Step 2/3: Downloading medical documents...
python document_downloader.py
if %ERRORLEVEL% NEQ 0 (
    echo Failed to download documents
    exit /b 1
)

echo.
echo Step 3/3: Building vector database...
python vector_store.py
if %ERRORLEVEL% NEQ 0 (
    echo Failed to build vector database
    exit /b 1
)

echo.
echo ====================================================================
echo Setup Complete!
echo ====================================================================
echo.
echo Your Medical RAG system is ready to use!
echo.
echo Next steps:
echo 1. Read INTEGRATION_GUIDE.md for integration options
echo 2. Test with: python rag_engine.py
echo 3. Integrate into your main project
echo ====================================================================

pause
