param(
    [string]$Out = "build"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$jdk = "C:\Program Files\Java\jdk-21.0.11\bin"
if (-not (Test-Path "$jdk\javac.exe")) {
    $jdk = Split-Path -Parent (Get-Command javac.exe).Source
}

$m2 = Join-Path $env:USERPROFILE ".m2\repository"
$paperApi = "$m2\io\papermc\paper\paper-api\1.20.1-R0.1-SNAPSHOT\paper-api-1.20.1-R0.1-SNAPSHOT.jar"
$bedwarsApi = "$m2\com\andrei1058\bedwars\bedwars-api\25.6\bedwars-api-25.6.jar"
$adventure = "$m2\net\kyori\adventure-api\4.14.0\adventure-api-4.14.0.jar"
$adventureKey = "$m2\net\kyori\adventure-key\4.14.0\adventure-key-4.14.0.jar"
$examination = "$m2\net\kyori\examination-api\1.3.0\examination-api-1.3.0.jar"
$bungeeChat = "$m2\net\md-5\bungeecord-chat\1.20-R0.1-deprecated+build.14\bungeecord-chat-1.20-R0.1-deprecated+build.14.jar"

foreach ($jar in @($paperApi, $bedwarsApi, $adventure, $adventureKey, $examination, $bungeeChat)) {
    if (-not (Test-Path $jar)) {
        throw "Missing compile dependency: $jar"
    }
}
$cp = @($paperApi, $bedwarsApi, $adventure, $adventureKey, $examination, $bungeeChat) -join ";"

$classes = Join-Path $Out "classes"
$jarFile = Join-Path $Out "BedWarsTeamSelector.jar"
if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Path $classes -Force | Out-Null

$sources = Get-ChildItem -Recurse (Join-Path $root "src\main\java") -Filter *.java | ForEach-Object { $_.FullName }
& "$jdk\javac.exe" -encoding UTF-8 --release 21 -Xlint:deprecation -cp $cp -d $classes $sources
if ($LASTEXITCODE -ne 0) { throw "javac failed" }

Copy-Item -Recurse (Join-Path $root "src\main\resources\*") $classes -Force
& "$jdk\jar.exe" --create --file $jarFile -C $classes .
if ($LASTEXITCODE -ne 0) { throw "jar failed" }

Write-Host "Built: $jarFile"
