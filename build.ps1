# VoiceFX 빌드: EXE(폴더) → 포터블 zip → 설치 프로그램
#   powershell -ExecutionPolicy Bypass -File build.ps1                  (버전은 voicefx/__init__.py)
#   powershell -ExecutionPolicy Bypass -File build.ps1 -SkipInstaller
#   powershell -ExecutionPolicy Bypass -File build.ps1 -OutDir dist-test   (dist의 VoiceFX를 실행 중일 때)
param([switch]$SkipInstaller, [string]$OutDir = "dist")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$version = (Select-String -Path voicefx\__init__.py -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
Write-Host "VoiceFX $version 빌드 → $OutDir"

$exePath = Join-Path (Resolve-Path . ) "$OutDir\VoiceFX\VoiceFX.exe"
if (Get-Process VoiceFX -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exePath }) {
    throw "$exePath 가 실행 중이라 덮어쓸 수 없습니다. VoiceFX를 닫거나 -OutDir 로 다른 폴더를 지정하세요."
}

python -m PyInstaller VoiceFX.spec --noconfirm --log-level WARN --distpath $OutDir --workpath "build\$OutDir"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 실패" }

Copy-Item LICENSE "$OutDir\VoiceFX\LICENSE.txt"  # GPL: 실행 파일과 함께 라이선스 전문 제공
$zip = "$OutDir\VoiceFX-$version-portable.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "$OutDir\VoiceFX" -DestinationPath $zip
Write-Host "포터블: $zip"

if (-not $SkipInstaller) {
    $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
              "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) { throw "Inno Setup 6이 없습니다: winget install JRSoftware.InnoSetup" }
    & $iscc /Q installer\VoiceFX.iss "/DAppVersion=$version" "/DDistDir=..\$OutDir"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup 실패" }
    Write-Host "설치 프로그램: $OutDir\VoiceFX-Setup-$version.exe"
}
