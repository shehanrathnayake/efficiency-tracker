# start.ps1
# Run before every work session:
#   cd C:\Users\ASUS\Documents\works\programs\efficiency-tracker
#   .\start.ps1

# 1. Load .env into current PowerShell session
#    Note: ANTHROPIC_API_KEY is intentionally NOT in .env
#    Claude Code uses subscription login — not an API key
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([^#][^=]*?)\s*=\s*(.*)\s*$') {
    [System.Environment]::SetEnvironmentVariable(
      $matches[1].Trim(), $matches[2].Trim(), 'Process'
    )
  }
}

# 2. Generate a fresh GitHub App token (valid 1 hour)
#    Uses gh extension Link-/gh-token — no Node.js or Python script needed
Write-Host "Generating GitHub App token..." -ForegroundColor Cyan

$tokenJson = gh token generate `
  --app-id $env:APP_ID `
  --key $env:PRIVATE_KEY_PATH `
  --installation-id $env:INSTALLATION_ID

if ($LASTEXITCODE -ne 0 -or -not $tokenJson) {
  Write-Host "Failed to generate token." -ForegroundColor Red
  Write-Host "Check APP_ID, INSTALLATION_ID, PRIVATE_KEY_PATH in .env" -ForegroundColor Yellow
  exit 1
}

# Extract just the token string from the JSON response
$env:GITHUB_TOKEN = ($tokenJson | ConvertFrom-Json).token

Write-Host "Token ready. Starting Claude Code (subscription mode)..." -ForegroundColor Green

# 3. Start Claude Code — uses subscription login, not API key
#    Run 'claude login' once if you haven't authenticated yet
claude