"""
배포용 zip 만들기 (v0.4 diff 방식).

파이프라인:
  1) python3 scripts/patch_workbook.py && python3 scripts/patch_dialogue.py   -> install/*.bundle (로컬 임시물)
  2) python3 scripts/build_diff_patch.py                                       -> install/patches/*.xd,*.meta
  3) python3 scripts/package_release.py                                        -> dist/MindsBeneathUsKorean.zip

zip 에는 install.ps1, uninstall.ps1, INSTALL.md, korean.pat(=patches/ + tools/ 를 묶은 zip)만 들어간다.
원본 게임 데이터나 통째 번들은 들어가지 않는다(안전장치: .bundle 이 있으면 중단).
이 스크립트는 3)만 수행하며, 1)·2)는 각각 실행해둬야 한다.
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(ROOT, "install")
DIST = os.path.join(ROOT, "dist", "MindsBeneathUsKorean.zip")
PAT = os.path.join(INSTALL, "korean.pat")
TOP = ["install.ps1", "uninstall.ps1", "INSTALL.md"]


def main():
    pat_files = []
    for sub in ("patches", "tools"):
        d = os.path.join(INSTALL, sub)
        if not os.path.isdir(d):
            raise SystemExit(f"install/{sub}/ 가 없음")
        for name in sorted(os.listdir(d)):
            pat_files.append((os.path.join(d, name), f"{sub}/{name}"))
    if not any(n == "tools/xdelta3.exe" for _, n in pat_files):
        raise SystemExit("tools/xdelta3.exe 가 없음")
    bad = [n for _, n in pat_files if n.endswith((".bundle", ".pat"))]
    if bad:
        raise SystemExit(f"통째 번들이 배포물에 들어가려 함: {bad}")

    # korean.pat = 확장자만 다른 zip (patches/ + tools/). install.ps1 이 임시 폴더에 풀어서 사용.
    with zipfile.ZipFile(PAT, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arc in pat_files:
            zf.write(src, arc)
    print(f"korean.pat: {len(pat_files)}개 파일, {os.path.getsize(PAT)} bytes")

    top = [(os.path.join(INSTALL, f), f) for f in TOP] + [(PAT, "korean.pat")]
    missing = [a for a, _ in top if not os.path.exists(a)]
    if missing:
        raise SystemExit(f"없는 파일: {missing}")
    os.makedirs(os.path.dirname(DIST), exist_ok=True)
    with zipfile.ZipFile(DIST, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arc in top:
            zf.write(src, arc, compress_type=zipfile.ZIP_STORED if arc.endswith(".pat") else zipfile.ZIP_DEFLATED)
            print("  담음:", arc)
    print(f"\n{DIST} ({os.path.getsize(DIST)} bytes)")


if __name__ == "__main__":
    main()
