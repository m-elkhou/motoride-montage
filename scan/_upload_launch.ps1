# Lance l'envoi YouTube des Shorts de meta/ (motif -Pattern) via upload_short.py.
# A lancer DETACHE pour survivre a la fermeture du terminal :
#   Start-Process powershell -ArgumentList '-NoProfile','-File','scan\_upload_launch.ps1' -WindowStyle Hidden
# Le journal des envois (meta/_uploaded.json) permet de relancer sans rien renvoyer deux fois.
param(
    [int]$RetryMin = 45,
    [int]$MaxHours = 30,
    [string]$Pattern = 'safe_*.json'
)
$Root = Split-Path -Parent $PSScriptRoot
$S2S = if ($env:MM_S2S_ROOT) { $env:MM_S2S_ROOT } else { Join-Path (Split-Path -Parent $Root) 'social2shorts' }
$Log = Join-Path $Root 'meta\upload.log'

$metas = Get-ChildItem (Join-Path $Root 'meta') -Filter $Pattern |
    Where-Object { $_.Name -notlike '_*' } | Sort-Object Name |
    ForEach-Object { $_.FullName -replace '\\', '/' }
if (-not $metas) { "Aucun meta ne correspond a '$Pattern'" | Tee-Object -FilePath $Log; exit 1 }

# uv run depuis le projet social2shorts : il fournit OAuth et le client YouTube.
Set-Location $S2S
& uv run python -X utf8 (Join-Path $Root 'upload_short.py') @metas --retry-min $RetryMin --max-hours $MaxHours *> $Log
