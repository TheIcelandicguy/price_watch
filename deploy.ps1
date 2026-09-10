# Thin wrapper - the real logic lives in E:\tools\deploy-to-ha.ps1
# Usage:  .\deploy.ps1          deploy
#         .\deploy.ps1 -DryRun  show what would change
param([switch]$DryRun)
& 'E:\tools\deploy-to-ha.ps1' -Domain 'price_watch' -Source "$PSScriptRoot\custom_components\price_watch" -DryRun:$DryRun
exit $LASTEXITCODE
