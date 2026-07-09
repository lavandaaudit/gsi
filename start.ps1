# Situational Awareness Platform - Startup Script

$PythonPath = "C:\Users\Sergey\AppData\Local\Programs\Python\Python39\python.exe"
$ScriptPath = Join-Path $PSScriptRoot "fetch_data.py"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  GLOBAL STATE INDEX (GSI) SITUATIONAL AWARENESS PLATFORM" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $PythonPath) {
    Write-Host "[1/3] Running Python Data Ingestion..." -ForegroundColor Green
    & $PythonPath $ScriptPath
    
    Write-Host ""
    Write-Host "[2/3] Starting Local Server on Port 8000..." -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow
    
    # Start the python HTTP server in the background
    $Job = Start-Job -ScriptBlock {
        param($py, $root)
        Set-Location $root
        & $py -m http.server 8000
    } -ArgumentList $PythonPath, $PSScriptRoot
    
    # Wait a moment for server to start
    Start-Sleep -Seconds 2
    
    Write-Host ""
    Write-Host "[3/3] Opening dashboard in browser..." -ForegroundColor Green
    Start-Process "http://localhost:8000/index.html"
    
    # Keep outputting job events or wait
    Write-Host "Server running. Logs will be recorded in background. To close, exit this window or terminate the task." -ForegroundColor Gray
    
    # Loop to check job status
    while ($Job.State -eq "Running") {
        Receive-Job -Job $Job -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 5
    }
} else {
    Write-Error "Python executable not found at $PythonPath. Please make sure Python is installed or check path."
}
