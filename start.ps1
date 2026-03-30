# Start LabelForge (backend + frontend) on Windows
$root = $PSScriptRoot

Write-Host "Starting backend..."
$backend = Start-Process -FilePath "$root\.venv\Scripts\uvicorn.exe" `
    -ArgumentList "backend.main:app", "--reload", "--port", "8000" `
    -WorkingDirectory $root `
    -PassThru

Write-Host "Starting frontend..."
$frontend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev" `
    -WorkingDirectory "$root\frontend" `
    -PassThru

Write-Host "Backend PID: $($backend.Id)"
Write-Host "Frontend PID: $($frontend.Id)"
Write-Host "Press Ctrl+C or close this window to stop."

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
}