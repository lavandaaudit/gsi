# ============================================================
# GSI — GitHub Deployment Script
# Usage: .\deploy_github.ps1 -Username "your-github-username" -Repo "gsi"
# ============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$Username,
    
    [string]$Repo = "gsi",
    
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot

Write-Host "`n📡 GSI · GitHub Deployment" -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor DarkGray
Write-Host "  Username : $Username" -ForegroundColor White
Write-Host "  Repo     : $Repo" -ForegroundColor White
Write-Host "  URL      : https://$Username.github.io/$Repo/" -ForegroundColor Green
Write-Host ""

# Check git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git is not installed. Install from https://git-scm.com/" -ForegroundColor Red
    exit 1
}

# Init or check existing repo
if (Test-Path (Join-Path $ProjectDir ".git")) {
    Write-Host "✅ Git repository already initialized." -ForegroundColor Green
} else {
    Write-Host "📦 Initializing git repository..." -ForegroundColor Yellow
    Set-Location $ProjectDir
    git init
    git branch -M main
}

# Create .gitignore
$gitignore = @"
__pycache__/
*.pyc
*.pyo
*.egg-info/
.env
*.log
"@
Set-Content -Path (Join-Path $ProjectDir ".gitignore") -Value $gitignore -Encoding UTF8
Write-Host "✅ .gitignore created." -ForegroundColor Green

# Make data folder tracked (add placeholder if history is too large)
$historyFile = Join-Path $ProjectDir "data\gsi_history.json"
if ((Get-Item $historyFile -ErrorAction SilentlyContinue).Length -gt 5MB) {
    Write-Host "⚠️  gsi_history.json is large (>5MB). Truncating for initial commit..." -ForegroundColor Yellow
    # Keep only last 100 entries
    $history = Get-Content $historyFile -Raw | ConvertFrom-Json
    $trimmed = $history | Select-Object -Last 100
    $trimmed | ConvertTo-Json -Depth 3 | Set-Content $historyFile -Encoding UTF8
}

# Stage all files
Set-Location $ProjectDir
git add .
git status

# Initial commit
Write-Host "`n📝 Creating initial commit..." -ForegroundColor Yellow
git commit -m "feat: GSI Situational Awareness Platform v1.0

128+ real signals from:
- NOAA SWPC (space weather)
- USGS Earthquake GeoJSON
- Yahoo Finance (20+ tickers)
- Open-Meteo (10 cities)
- Google News RSS
- ReliefWeb RSS
- Wikimedia Pageviews API
- Global DNS latency

GitHub Actions auto-updates every 15 minutes.
"

# Add remote
$remoteUrl = "https://github.com/$Username/$Repo.git"
$existingRemote = git remote get-url origin 2>$null
if ($existingRemote) {
    Write-Host "  Remote already set: $existingRemote" -ForegroundColor DarkGray
    git remote set-url origin $remoteUrl
} else {
    git remote add origin $remoteUrl
}
Write-Host "✅ Remote set to: $remoteUrl" -ForegroundColor Green

# Push
Write-Host "`n🚀 Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "   (You may be prompted for GitHub credentials)" -ForegroundColor DarkGray
git push -u origin main

Write-Host "`n✅ DONE! Next steps:" -ForegroundColor Green
Write-Host ""
Write-Host "  1. Go to: https://github.com/$Username/$Repo/settings/pages" -ForegroundColor White
Write-Host "     → Source: Deploy from branch" -ForegroundColor DarkGray
Write-Host "     → Branch: main / (root)" -ForegroundColor DarkGray
Write-Host "     → Click Save" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  2. Wait ~60 seconds, then visit:" -ForegroundColor White
Write-Host "     🌐 https://$Username.github.io/$Repo/" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. GitHub Actions will auto-update data every 15 minutes." -ForegroundColor White
Write-Host "     Check: https://github.com/$Username/$Repo/actions" -ForegroundColor DarkGray
Write-Host ""

if ($OpenBrowser) {
    Start-Process "https://github.com/$Username/$Repo/settings/pages"
}
