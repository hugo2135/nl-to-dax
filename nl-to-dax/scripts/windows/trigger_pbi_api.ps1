param(
    [Parameter(Mandatory=$true)]
    [string]$WorkspaceRoot,
    [Parameter(Mandatory=$true)]
    [string]$PbiConfigId,
    [Parameter(Mandatory=$true)]
    [string]$DaxQueryFile,
    [string]$OutputCsvPath = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$PbiQueryDir = Join-Path $WorkspaceRoot "pbi_query"
New-Item -ItemType Directory -Force -Path $PbiQueryDir | Out-Null

if (-not $OutputCsvPath) {
    $OutputCsvPath = Join-Path $PbiQueryDir "query_result.csv"
}

$PythonScript = Join-Path $ScriptDir "..\shared\pbi_api_client.py"

python $PythonScript $WorkspaceRoot $PbiConfigId $DaxQueryFile $OutputCsvPath
