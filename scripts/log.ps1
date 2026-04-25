# reflect — PowerShell `log` function.
#
# Dot-source this file from your PowerShell profile to get a `log` command in
# every session:
#
#     . C:\path\to\efficiency-tracker\scripts\log.ps1
#
# Usage:
#     log meeting 30 "standup"
#     log testing 90 "pre-merge session"
#     log tasks "bank details crud, login fix"      # duration defaults to 1
#     log reflect "rework spike was from yesterday" # duration defaults to 1
#
# Writes CSV-quoted rows (no BOM) to %USERPROFILE%\.reflect\log.csv.

function log {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true, Position = 0)]
        [string]$Category,

        [Parameter(Mandatory = $true, Position = 1)]
        [string]$Arg2,

        [Parameter(Position = 2)]
        [string]$Arg3
    )

    # If Arg2 is numeric, it's the duration and Arg3 is the note.
    # Otherwise Arg2 IS the note (duration defaults to 1 — used for `tasks`,
    # `reflect`, `merge_event`, etc., where duration isn't meaningful).
    $parsed = 0
    if ([int]::TryParse($Arg2, [ref]$parsed)) {
        $duration = $parsed
        $note = if ($PSBoundParameters.ContainsKey('Arg3')) { $Arg3 } else { "" }
    } else {
        $duration = 1
        $note = $Arg2
        if ($PSBoundParameters.ContainsKey('Arg3') -and $Arg3) {
            $note = "$note $Arg3"
        }
    }

    $dir = Join-Path $env:USERPROFILE ".reflect"
    $path = Join-Path $dir "log.csv"
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $now = Get-Date
    $dateStr = $now.ToString("yyyy-MM-dd")
    $timeStr = $now.ToString("HH:mm")

    # CSV-quote the note if it contains comma, double-quote, or newline.
    if ($note -match '[",\r\n]') {
        $noteEsc = '"' + ($note -replace '"', '""') + '"'
    } else {
        $noteEsc = $note
    }

    $line = "$dateStr,$timeStr,$duration,$Category,$noteEsc`r`n"

    # Plain UTF-8 without BOM so the Python reader gets clean rows on every append.
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::AppendAllText($path, $line, $utf8)

    Write-Host ("logged: {0}" -f $line.TrimEnd())
}
