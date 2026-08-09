"""
install/*.bundle 파일들을 install/korean.pat 하나로 묶고, 낱개 .bundle 파일은 지운다.
patch_workbook.py / patch_dialogue.py 로 install/ 에 번들을 다 만든 다음 마지막에 이걸 실행할 것.

korean.pat 은 확장자만 다를 뿐 내용은 그냥 zip 파일이다 (install.ps1 이 임시로 .zip 으로
바꿔서 Expand-Archive로 푼다). 확장자를 .zip이 아니게 한 이유는 사용자가 탐색기에서 실수로
더블클릭해서 풀어버리는 걸 방지하기 위함 — install.ps1을 통해서만 설치되도록 유도.

install/ 안에는 최종적으로 install.ps1, uninstall.ps1, INSTALL.md, korean.pat 만 남는다.
"""
import os
import zipfile
import glob

PROJECT_ROOT = "/Users/sahncha/Projects/MindsBeneathUsKorean"
INSTALL_DIR = os.path.join(PROJECT_ROOT, "install")
ZIP_PATH = os.path.join(INSTALL_DIR, "korean.pat")


def main():
    bundle_paths = sorted(glob.glob(os.path.join(INSTALL_DIR, "*.bundle")))

    if not bundle_paths:
        print("install/ 안에 .bundle 파일이 없음 — 먼저 patch_workbook.py / patch_dialogue.py 실행할 것.")
        return

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in bundle_paths:
            arcname = os.path.basename(path)
            zf.write(path, arcname)
            print(f"  담음: {arcname}")

    for path in bundle_paths:
        os.remove(path)

    print()
    print(f"저장 완료: {ZIP_PATH} ({os.path.getsize(ZIP_PATH)} bytes, {len(bundle_paths)}개 파일)")
    print(f"낱개 .bundle 파일 {len(bundle_paths)}개 삭제함 — install/ 안엔 이제 korean.pat만 있음.")


if __name__ == "__main__":
    main()
