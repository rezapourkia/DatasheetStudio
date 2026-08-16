param(
    [Parameter(Mandatory = $true)]
    [string]$BuiltArtifact,
    [Parameter(Mandatory = $true)]
    [string]$InstalledPluginDirectory
)

$ErrorActionPreference = "Stop"

function Get-RelativeChildPath {
    param([string]$BasePath, [string]$ChildPath)
    $BaseFull = [IO.Path]::GetFullPath($BasePath).TrimEnd("\") + "\"
    $ChildFull = [IO.Path]::GetFullPath($ChildPath)
    if (-not $ChildFull.StartsWith($BaseFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside expected root: $ChildFull"
    }
    $ChildFull.Substring($BaseFull.Length)
}

$BuiltItem = Get-Item -LiteralPath (Resolve-Path -LiteralPath $BuiltArtifact).Path
$PluginDir = (Resolve-Path -LiteralPath $InstalledPluginDirectory).Path
$SettingsPath = Join-Path $PluginDir "settings.xml"
if (-not (Test-Path -LiteralPath $SettingsPath -PathType Leaf)) {
    throw "settings.xml not found: $SettingsPath"
}

[xml]$Settings = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8
$ExeFile = [string]$Settings.Source.ExeFile
if ([string]::IsNullOrWhiteSpace($ExeFile) -or
    -not $ExeFile.EndsWith(".exe", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "settings.xml must name the exact root executable in Source@ExeFile"
}

$Installed = Join-Path $PluginDir $ExeFile
if (-not (Test-Path -LiteralPath $Installed -PathType Leaf)) {
    throw "Manifest target not found: $Installed"
}

$BuiltRoot = if ($BuiltItem.PSIsContainer) {
    $BuiltItem.FullName
} else {
    Split-Path -Parent $BuiltItem.FullName
}
$BuiltFiles = if ($BuiltItem.PSIsContainer) {
    @(Get-ChildItem -LiteralPath $BuiltRoot -Recurse -File -Force)
} else {
    @($BuiltItem)
}
if ($BuiltFiles.Count -eq 0) {
    throw "Built artifact contains no files"
}

$ExpectedRelative = @{}
$Verified = foreach ($BuiltFile in $BuiltFiles) {
    $Relative = Get-RelativeChildPath $BuiltRoot $BuiltFile.FullName
    $ExpectedRelative[$Relative.ToLowerInvariant()] = $Relative
    $InstalledFile = Join-Path $PluginDir $Relative
    if (-not (Test-Path -LiteralPath $InstalledFile -PathType Leaf)) {
        throw "Installed artifact is missing: $Relative"
    }
    $BuiltHash = (Get-FileHash -LiteralPath $BuiltFile.FullName -Algorithm SHA256).Hash
    $InstalledHash = (Get-FileHash -LiteralPath $InstalledFile -Algorithm SHA256).Hash
    if ($BuiltHash -ne $InstalledHash) {
        throw "Installed artifact differs from tested build: $Relative"
    }
    $Relative
}
if (-not $ExpectedRelative.ContainsKey($ExeFile.ToLowerInvariant())) {
    throw "Built artifact does not contain settings.xml@ExeFile: $ExeFile"
}

$AllowedInstalled = @{ "settings.xml" = "settings.xml" }
foreach ($Relative in $ExpectedRelative.Values) {
    $AllowedInstalled[$Relative.ToLowerInvariant()] = $Relative
}
$Unexpected = @(Get-ChildItem -LiteralPath $PluginDir -Recurse -File -Force | Where-Object {
    $Relative = Get-RelativeChildPath $PluginDir $_.FullName
    -not $AllowedInstalled.ContainsKey($Relative.ToLowerInvariant())
} | ForEach-Object {
    Get-RelativeChildPath $PluginDir $_.FullName
})
if ($Unexpected.Count -gt 0) {
    throw "Installed folder has unexpected/stale files: $($Unexpected -join ', ')"
}

$RootExecutables = @(Get-ChildItem -LiteralPath $PluginDir -Filter *.exe -File -Force)
if ($RootExecutables.Count -ne 1) {
    throw "Keep exactly one intended root EXE in the plug-in folder; found $($RootExecutables.Count)"
}

[pscustomobject]@{
    Settings = $SettingsPath
    ExeFile = $ExeFile
    Installed = $Installed
    ExecutableSHA256 = (Get-FileHash -LiteralPath $Installed -Algorithm SHA256).Hash
    VerifiedFileCount = @($Verified).Count
    UnexpectedFileCount = $Unexpected.Count
    RootExecutableCount = $RootExecutables.Count
}
