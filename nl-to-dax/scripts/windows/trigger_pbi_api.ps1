param(
    [Parameter(Mandatory=$true)]
    [string]$PbiConfigId,
    [Parameter(Mandatory=$true)]
    [string]$DaxQueryFile,
    [string]$OutputCsvPath = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 往上找到包含 .claude/ 的目錄作為工作區根目錄
$WorkspaceRoot = $ScriptDir
while ($WorkspaceRoot -ne (Split-Path -Parent $WorkspaceRoot)) {
    if (Test-Path (Join-Path $WorkspaceRoot ".claude")) { break }
    $WorkspaceRoot = Split-Path -Parent $WorkspaceRoot
}

$PbiQueryDir = Join-Path $WorkspaceRoot "pbi_query"
New-Item -ItemType Directory -Force -Path $PbiQueryDir | Out-Null

if (-not $OutputCsvPath) {
    $OutputCsvPath = Join-Path $PbiQueryDir "query_result.csv"
}

$PythonScript = Join-Path $ScriptDir "..\shared\pbi_api_client.py"

python $PythonScript $PbiConfigId $DaxQueryFile $OutputCsvPath
