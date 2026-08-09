# Minds Beneath Us 한글패치 설치 방법

## 설치

1. 다운로드한 `install` 폴더(`install.ps1`, `uninstall.ps1`, `INSTALL.md`, `korean.pat` 이 들어있는
   폴더) 전체를 아무 곳이나 압축을 풀어둡니다. 게임 폴더 안에 안 넣어도 됩니다.
   (`korean.pat`은 그대로 두세요 — `install.ps1`이 알아서 풀어서 설치합니다.)
2. `install.ps1` 을 우클릭 → **"PowerShell로 실행"** 을 선택합니다.
   - 게임 설치 경로를 자동으로 찾아서 알려줍니다. 못 찾으면 직접 경로를 입력하라고 물어봅니다
     (`MindsBeneathUs.exe` 가 있는 폴더 경로).
   - 실행하면 기존 원본 파일을 자동으로 `_originals_backup` 폴더에 백업한 뒤, 패치 파일로 덮어씁니다.
3. 게임을 실행하고 **설정(Settings) → 언어(Language) → English** 를 선택하면 한글로 표시됩니다.
   (원래 영어 슬롯이었던 자리를 대체한 것입니다. 일본어를 포함한 다른 언어는 전혀 손대지 않았습니다.)

### PowerShell 실행이 안 될 때

윈도우 보안 정책 때문에 스크립트 실행이 막혀있을 수 있습니다. PowerShell을 관리자 권한으로 열고
아래 명령어를 한 번 실행한 뒤 다시 시도해주세요:

```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 제거

`uninstall.ps1` 을 우클릭 → "PowerShell로 실행" 하면 백업해둔 원본 파일로 자동 복원됩니다.

## 스크립트 없이 수동 설치하고 싶다면

`korean.pat`은 확장자만 다를 뿐 내용물은 일반 zip 파일입니다. 파일명을 `korean.zip`으로 바꾸면
탐색기나 압축 프로그램으로 바로 풀 수 있습니다. 그렇게 풀어서 나오는 `.bundle` 파일들을 직접
아래 경로에 복사해 넣어도 됩니다 (파일명은 그대로 유지, 기존 파일 덮어쓰기):

```
[게임 설치 폴더]\MindsBeneathUs_Data\StreamingAssets\aa\StandaloneWindows64\
```

이 경우 원본 백업은 직접 해두시길 권장합니다.

## 주의사항

- `.dll`/`.exe` 파일은 전혀 건드리지 않습니다. 오직 데이터 파일(`.bundle`)만 교체합니다.
- 알려진 문제: 게임 시작 직후 나오는 타이틀 화면의 일부 버튼(New Game/Continue/Settings 등)은
  한글이 아닌 영어 원문으로 고정되어 나올 수 있습니다. 인게임(ESC 메뉴 등) 텍스트와 대사는 정상 작동합니다.
- 게임이 업데이트되면 이 패치가 안 맞을 수 있습니다. 그런 경우 게임 실행이 안 되거나 이상해지면
  `uninstall.ps1` 로 원본 복원 후 패치 업데이트를 기다려주세요.

## 문의 / 버그 제보

어색한 번역이나 버그를 발견하시면 GitHub Issues에 남겨주세요.
