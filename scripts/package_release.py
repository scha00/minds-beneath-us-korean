"""
1. install/*.bundle 파일들을 install/korean.pat 하나로 묶고, 낱개 .bundle 파일은 지운다.
2. install/install.ps1, uninstall.ps1, INSTALL.md, korean.pat 을 전부 다시
   dist/MindsBeneathUsKorean.zip 하나로 묶는다 (GitHub Release에 파일 하나만 올리면 되게).

patch_workbook.py / patch_dialogue.py 로 install/ 에 번들을 다 만든 다음 마지막에 이걸 실행할 것.

install/ 안에는 최종적으로 install.ps1, uninstall.ps1, INSTALL.md, korean.pat 만 남는다.
dist/MindsBeneathUsKorean.zip 이 실제로 Release에 올리는 파일 (이 zip 안에 위 4개 파일이 그대로 들어있음,
사용자가 풀면 install.ps1 등이 바로 나옴 — 감싸는 폴더 없음).

korean.pat 은 확장자만 다를 뿐 내용은 그냥 zip 파일이다 (install.ps1 이 임시로 .zip 으로
바꿔서 Expand-Archive로 푼다). 확장자를 .zip이 아니게 한 이유는 사용자가 탐색기에서 실수로
더블클릭해서 풀어버리는 걸 방지하기 위함 — install.ps1을 통해서만 설치되도록 유도.
dist/MindsBeneathUsKorean.zip 은 반대로 진짜 .zip 이 맞음 — 이건 사용자가 직접 풀어야 하는 배포 파일.
"""
import os
import zipfile
import glob

PROJECT_ROOT = "/Users/sahncha/Projects/MindsBeneathUsKorean"
INSTALL_DIR = os.path.join(PROJECT_ROOT, "install")
PAT_PATH = os.path.join(INSTALL_DIR, "korean.pat")

DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
DIST_ZIP_PATH = os.path.join(DIST_DIR, "MindsBeneathUsKorean.zip")

DIST_FILES = ["install.ps1", "uninstall.ps1", "INSTALL.md", "korean.pat"]


def package_bundles():
    bundle_paths = sorted(glob.glob(os.path.join(INSTALL_DIR, "*.bundle")))

    if not bundle_paths:
        print("install/ 안에 .bundle 파일이 없음 — 먼저 patch_workbook.py / patch_dialogue.py 실행할 것.")
        return False

    with zipfile.ZipFile(PAT_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in bundle_paths:
            arcname = os.path.basename(path)
            zf.write(path, arcname)
            print(f"  담음(korean.pat): {arcname}")

    for path in bundle_paths:
        os.remove(path)

    print(f"저장 완료: {PAT_PATH} ({os.path.getsize(PAT_PATH)} bytes, {len(bundle_paths)}개 파일)")
    print(f"낱개 .bundle 파일 {len(bundle_paths)}개 삭제함 — install/ 안엔 이제 korean.pat만 있음.")
    return True


def package_dist_zip():
    os.makedirs(DIST_DIR, exist_ok=True)

    missing = [f for f in DIST_FILES if not os.path.exists(os.path.join(INSTALL_DIR, f))]
    if missing:
        print(f"오류: install/ 안에 없는 파일: {missing}")
        return

    # ZIP_STORED for korean.pat (이미 압축된 zip이라 다시 압축해봐야 의미 없음), 나머지는 압축.
    with zipfile.ZipFile(DIST_ZIP_PATH, "w") as zf:
        for fname in DIST_FILES:
            src = os.path.join(INSTALL_DIR, fname)
            method = zipfile.ZIP_STORED if fname.endswith(".pat") else zipfile.ZIP_DEFLATED
            zf.write(src, fname, compress_type=method)
            print(f"  담음(dist zip): {fname}")

    print()
    print(f"배포용 zip 저장 완료: {DIST_ZIP_PATH} ({os.path.getsize(DIST_ZIP_PATH)} bytes)")
    print("이 파일 하나를 GitHub Release에 올리면 됨 (gh release upload ... dist/MindsBeneathUsKorean.zip --clobber)")


def main():
    if package_bundles():
        package_dist_zip()


if __name__ == "__main__":
    main()
