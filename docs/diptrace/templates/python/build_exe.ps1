param(
    [Parameter(Mandatory = $true)]
    [string]$PythonExe,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedPythonVersion,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedPyInstallerVersion,
    [ValidateSet("32", "64")]
    [string]$ExpectedPythonBits = "64",
    [string]$SourceFile = "plugin_main.py",
    [string]$Name = "MyPlugin",
    [ValidateSet("onefile", "onedir")]
    [string]$Bundle = "onedir"
)

$ErrorActionPreference = "Stop"

function Get-RelativeChildPath {
    param([string]$BasePath, [string]$ChildPath)
    $BaseFull = [IO.Path]::GetFullPath($BasePath).TrimEnd("\") + "\"
    $ChildFull = [IO.Path]::GetFullPath($ChildPath)
    if (-not $ChildFull.StartsWith($BaseFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside artifact root: $ChildFull"
    }
    $ChildFull.Substring($BaseFull.Length)
}

$TemplateDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ResolvedSource = Join-Path $TemplateDir $SourceFile
$BuildDir = Join-Path $TemplateDir ".build"
$DistDir = Join-Path $TemplateDir "dist"

$PythonBits = & $PythonExe -c "import struct; print(struct.calcsize('P') * 8)"
if ($LASTEXITCODE -ne 0 -or $PythonBits.Trim() -ne $ExpectedPythonBits) {
    throw "Python bitness is $($PythonBits.Trim()); expected $ExpectedPythonBits"
}
$PythonVersion = & $PythonExe -c "import platform; print(platform.python_version())"
if ($LASTEXITCODE -ne 0 -or $PythonVersion.Trim() -ne $ExpectedPythonVersion) {
    throw "Python version is $($PythonVersion.Trim()); expected $ExpectedPythonVersion"
}
$PyInstallerVersion = & $PythonExe -m PyInstaller --version
if ($LASTEXITCODE -ne 0 -or $PyInstallerVersion.Trim() -ne $ExpectedPyInstallerVersion) {
    throw "PyInstaller version is $($PyInstallerVersion.Trim()); expected $ExpectedPyInstallerVersion"
}

$BundleFlag = if ($Bundle -eq "onefile") { "--onefile" } else { "--onedir" }
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    $BundleFlag `
    --noconsole `
    --name $Name `
    --distpath $DistDir `
    --workpath (Join-Path $BuildDir "work") `
    --specpath $BuildDir `
    $ResolvedSource

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$Executable = if ($Bundle -eq "onefile") {
    Join-Path $DistDir "$Name.exe"
} else {
    Join-Path (Join-Path $DistDir $Name) "$Name.exe"
}
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Expected executable was not created: $Executable"
}

$Artifact = Get-Item -LiteralPath $Executable
$Hash = Get-FileHash -LiteralPath $Executable -Algorithm SHA256
$ArtifactRoot = if ($Bundle -eq "onefile") {
    $Artifact.FullName
} else {
    Split-Path -Parent $Artifact.FullName
}
$ManifestRoot = if ($Bundle -eq "onefile") {
    Split-Path -Parent $Artifact.FullName
} else {
    $ArtifactRoot
}
$ArtifactFiles = if ($Bundle -eq "onefile") {
    @($Artifact)
} else {
    @(Get-ChildItem -LiteralPath $ArtifactRoot -Recurse -File -Force)
}
$ManifestFiles = @($ArtifactFiles | ForEach-Object {
    [pscustomobject]@{
        Path = Get-RelativeChildPath $ManifestRoot $_.FullName
        Size = $_.Length
        SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
})
$ManifestPath = Join-Path $DistDir "$Name.artifact-sha256.json"
$Manifest = [ordered]@{
    Schema = 1
    Name = $Name
    Bundle = $Bundle
    PythonVersion = $PythonVersion.Trim()
    PythonBits = $PythonBits.Trim()
    PyInstallerVersion = $PyInstallerVersion.Trim()
    Artifact = $ArtifactRoot
    Files = $ManifestFiles
} | ConvertTo-Json -Depth 5
[Text.Encoding]$Utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText(
    $ManifestPath,
    $Manifest + [Environment]::NewLine,
    $Utf8NoBom
)
[pscustomobject]@{
    Executable = $Artifact.FullName
    Artifact = $ArtifactRoot
    Size = $Artifact.Length
    ExecutableSHA256 = $Hash.Hash
    PythonBits = $PythonBits.Trim()
    PythonVersion = $PythonVersion.Trim()
    PyInstallerVersion = $PyInstallerVersion.Trim()
    Bundle = $Bundle
    ArtifactManifest = $ManifestPath
}
