param(
    [Parameter(Mandatory=$true)]
    [string]$WorkspaceRoot,
    [Parameter(Mandatory=$true)]
    [string]$PbiConfigId
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "..\shared\model_overview.py"

python $PythonScript $WorkspaceRoot $PbiConfigId
