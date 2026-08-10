# Minds Beneath Us 한글패치 설치 스크립트
#
# 이 스크립트와 같은 폴더에 있는 korean.pat(내용물은 zip, 탐색기에서 실수로 못 풀게 확장자만
# 다르게 한 것)을 임시 폴더에 풀고, 그 안의 .bundle 파일들을 게임의
# StreamingAssets\aa\StandaloneWindows64\ 폴더로 복사한다.
# 덮어쓰기 전에 기존(원본) 파일은 자동으로 _originals_backup\ 폴더에 백업해둔다.
# (이미 백업이 있으면 다시 백업하지 않음 — 원본이 패치본으로 덮어써지는 걸 막기 위함)
#
# 사용법: 이 스크립트를 korean.pat 과 같은 폴더에 두고 실행하면 됨.
#         게임 설치 경로를 자동으로 못 찾으면 직접 입력하라고 물어봄.

$ErrorActionPreference = "Stop"

# 콘솔이 한글을 깨진 문자로 표시하는 걸 막기 위해 출력 인코딩을 UTF-8로 강제.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    chcp 65001 > $null
} catch {}

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

Write-Host "=== Minds Beneath Us 한글패치 설치 ===" -ForegroundColor Cyan
Write-Host ""

$gameRoot = Find-GameRoot
if (-not $gameRoot) {
    Write-Host "게임 설치 폴더를 자동으로 못 찾았어요."
    $gameRoot = Read-Host "MindsBeneathUs.exe가 있는 폴더 경로를 직접 입력해주세요 (예: D:\Steam\steamapps\common\MindsBeneathUs)"
}

$targetDir = Join-Path $gameRoot "MindsBeneathUs_Data\StreamingAssets\aa\StandaloneWindows64"

if (-not (Test-Path $targetDir)) {
    Write-Host "오류: 대상 폴더를 찾을 수 없습니다: $targetDir" -ForegroundColor Red
    Write-Host "게임 설치 경로가 맞는지 확인해주세요."
    Read-Host "이 창을 닫으려면 Enter 키를 누르세요"
    exit 1
}

Write-Host "게임 폴더: $gameRoot"
Write-Host "대상 위치: $targetDir"
Write-Host ""

$scriptDir = $PSScriptRoot
$patPath = Join-Path $scriptDir "korean.pat"

if (-not (Test-Path $patPath)) {
    Write-Host "오류: korean.pat 을 찾을 수 없습니다 ($patPath)." -ForegroundColor Red
    Write-Host "이 스크립트를 korean.pat 과 같은 폴더에 두고 실행해주세요."
    Read-Host "이 창을 닫으려면 Enter 키를 누르세요"
    exit 1
}

$tempExtractDir = Join-Path $env:TEMP "mbu_kr_patch_$(Get-Random)"
New-Item -ItemType Directory -Path $tempExtractDir | Out-Null

# Expand-Archive 는 확장자가 .zip 이어야 동작하는 버전이 있어서, 임시로 .zip 사본을 만들어서 푼다.
$tempZipPath = Join-Path $tempExtractDir "korean.zip"
Copy-Item -Path $patPath -Destination $tempZipPath

Write-Host "패치 파일 압축 해제 중..."
Expand-Archive -Path $tempZipPath -DestinationPath $tempExtractDir -Force
Remove-Item -Path $tempZipPath -Force

$backupDir = Join-Path $targetDir "_originals_backup"
$bundleFiles = Get-ChildItem -Path $tempExtractDir -Filter "*.bundle"

if ($bundleFiles.Count -eq 0) {
    Write-Host "오류: korean.pat 안에 .bundle 파일이 없습니다." -ForegroundColor Red
    Remove-Item -Path $tempExtractDir -Recurse -Force
    Read-Host "이 창을 닫으려면 Enter 키를 누르세요"
    exit 1
}

# 백업 폴더가 이번 실행 전부터 있었는지로 "처음 설치"인지 "재설치/업데이트"인지 판단.
$hadExistingInstall = Test-Path $backupDir

if ($hadExistingInstall) {
    Write-Host "기존 설치가 감지되었습니다 — 업데이트를 진행합니다." -ForegroundColor Yellow
} else {
    Write-Host "처음 설치합니다."
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}
Write-Host ""

$backedUp = 0
$installed = 0
$skipped = @()

foreach ($file in $bundleFiles) {
    $originalPath = Join-Path $targetDir $file.Name
    $backupPath = Join-Path $backupDir $file.Name

    if (-not (Test-Path $originalPath)) {
        Write-Host "  [건너뜀] 원본에 없는 파일: $($file.Name)" -ForegroundColor Yellow
        $skipped += $file.Name
        continue
    }

    if (-not (Test-Path $backupPath)) {
        Copy-Item -Path $originalPath -Destination $backupPath
        $backedUp++
    }

    Copy-Item -Path $file.FullName -Destination $originalPath -Force
    $installed++
    Write-Host "  [설치됨] $($file.Name)"
}

Remove-Item -Path $tempExtractDir -Recurse -Force

Write-Host ""
if (-not $hadExistingInstall) {
    Write-Host "완료: 새로 설치되었습니다. ($installed 개 파일)" -ForegroundColor Green
} elseif ($backedUp -eq 0) {
    Write-Host "완료: 기존 설치를 최신 버전으로 업데이트했습니다. ($installed 개 파일, 새로 백업된 파일 없음)" -ForegroundColor Green
} else {
    Write-Host "완료: 기존 설치를 업데이트했습니다. ($installed 개 파일 중 $backedUp 개는 이번에 새로 추가되어 처음 백업됨)" -ForegroundColor Green
}
Write-Host "백업 위치: $backupDir"

# 설치 결과를 파일로도 남겨서, 콘솔 창이 바로 닫히거나 스크롤을 놓쳐도 나중에 확인할 수 있게 함.
$logPath = Join-Path $scriptDir "install_log.txt"
$logLines = @(
    "설치 시각: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "게임 폴더: $gameRoot"
    "설치됨: $installed 개"
    "건너뜀: $($skipped.Count) 개"
)
if ($skipped.Count -gt 0) {
    $logLines += "건너뛴 파일 목록 (게임이 패치 제작 당시와 다른 버전이면 발생할 수 있음 — 이 파일들은 패치가 적용되지 않음):"
    $logLines += ($skipped | ForEach-Object { "  - $_" })
}
$logLines | Out-File -FilePath $logPath -Encoding UTF8
Write-Host "설치 로그 저장됨: $logPath"

if ($skipped.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠경고: $($skipped.Count)개 파일이 건너뛰어졌습니다 — 해당 부분은 패치가 적용되지 않아 원문(중국어 등)이 그대로 나올 수 있습니다." -ForegroundColor Red
    Write-Host "  게임이 패치 제작 당시와 다른 버전으로 업데이트되어 리소스 파일명이 바뀌었을 가능성이 있습니다."
    Write-Host "  install_log.txt 파일을 개발자에게 보내주시면 도움이 됩니다."
}

Write-Host ""
Write-Host "게임 실행 후 설정 > 언어 > English 로 변경하면 한글이 나옵니다."
Write-Host "제거하려면 uninstall.ps1 을 실행하세요."
Write-Host ""
Read-Host "이 창을 닫으려면 Enter 키를 누르세요"
