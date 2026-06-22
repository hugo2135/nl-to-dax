param(
    [Parameter(Mandatory=$true)]
    [string]$InputPath
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "..\shared\chunk_model.py"

python $PythonScript $InputPath
