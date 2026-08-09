# Minds Beneath Us 한글패치 제거 스크립트
#
# install.ps1 이 만들어둔 _originals_backup\ 폴더의 원본 파일들을 다시 복원하고,
# 백업 폴더를 정리한다.

$ErrorActionPreference = "Stop"

function Find-GameRoot {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Steam\steamapps\common\MindsBeneathUs",
        "${env:ProgramFiles}\Steam\steamapps\common\MindsBeneathUs",
        "C:\Steam\steamapps\common\MindsBeneathUs",
        "D:\Steam\steamapps\common\MindsBeneathUs",
        "E:\Steam\steamapps\common\MindsBeneathUs"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "MindsBeneathUs_Data")) {
            return $c
        }
    }
    return $null
}

Write-Host "=== Minds Beneath Us 한글패치 제거 ===" -ForegroundColor Cyan
Write-Host ""

$gameRoot = Find-GameRoot
if (-not $gameRoot) {
    Write-Host "게임 설치 폴더를 자동으로 못 찾았어요."
    $gameRoot = Read-Host "MindsBeneathUs.exe가 있는 폴더 경로를 직접 입력해주세요"
}

$targetDir = Join-Path $gameRoot "MindsBeneathUs_Data\StreamingAssets\aa\StandaloneWindows64"
$backupDir = Join-Path $targetDir "_originals_backup"

if (-not (Test-Path $backupDir)) {
    Write-Host "백업 폴더가 없습니다: $backupDir" -ForegroundColor Red
    Write-Host "패치가 설치되어 있지 않거나 이미 제거된 것 같습니다."
    exit 1
}

$backupFiles = Get-ChildItem -Path $backupDir -Filter "*.bundle"
$restored = 0

foreach ($file in $backupFiles) {
    $targetPath = Join-Path $targetDir $file.Name
    Copy-Item -Path $file.FullName -Destination $targetPath -Force
    $restored++
    Write-Host "  [복원됨] $($file.Name)"
}

Remove-Item -Path $backupDir -Recurse -Force

Write-Host ""
Write-Host "완료: $restored 개 파일 원본으로 복원됨. 백업 폴더 삭제됨." -ForegroundColor Green
Write-Host "한글패치가 완전히 제거되었습니다."
