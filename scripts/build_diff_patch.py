"""
diff 패치 빌드: 원본 번들(resource/)과 우리가 만든 번들의 '압축 푼 데이터 스트림'을 xdelta3로 비교해
install/patches/ 에 <번들명>.xd + <번들명>.meta 를 만든다. 원본 게임 데이터는 들어가지 않는다
(바뀐 부분과 복사 지시만 담김). meta에는 원본 파일의 sha256(게임 버전 확인용), 새 스트림의 sha256,
노드 목록(이름/크기/플래그)이 들어간다.

    python3 scripts/build_diff_patch.py [번들이 있는 폴더(기본 install/)]

번들 폴더에는 patch_workbook.py / patch_dialogue.py 가 만든 *.bundle 이 있어야 한다.
"""
import glob
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bundlefs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCE = os.path.join(ROOT, "resource")
OUT = os.path.join(ROOT, "install", "patches")
TMP = os.path.join(ROOT, "review", "_tmp_diff")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "install")
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    total = 0
    for path in sorted(glob.glob(os.path.join(src, "*.bundle"))):
        name = os.path.basename(path)
        orig_path = os.path.join(RESOURCE, name)
        orig_raw = open(orig_path, "rb").read()
        o = bundlefs.parse(orig_path)
        n = bundlefs.parse(path)
        off = 0
        for noff, nsz, _f, _n in n["nodes"]:
            assert noff == off, f"{name}: 노드 오프셋이 연속이 아님"
            off += nsz
        assert off == len(n["stream"])
        so, sn, xd = (os.path.join(TMP, x) for x in ("so", "sn", "x.xd"))
        open(so, "wb").write(o["stream"])
        open(sn, "wb").write(n["stream"])
        subprocess.run(["xdelta3", "-e", "-9", "-S", "none", "-B", "1073741824", "-W", "67108864",
                        "-f", "-s", so, sn, xd], check=True, capture_output=True)
        os.replace(xd, os.path.join(OUT, name + ".xd"))
        lines = [
            f"orig_sha256={sha256(orig_raw)}",
            f"stream_sha256={sha256(n['stream'])}",
            f"stream_size={len(n['stream'])}",
            f"version={n['version']}",
            f"player={n['player']}",
            f"engine={n['engine']}",
        ]
        for _o, sz, f, nm in n["nodes"]:
            lines.append(f"node\t{f}\t{sz}\t{nm}")
        open(os.path.join(OUT, name + ".meta"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        s = os.path.getsize(os.path.join(OUT, name + ".xd"))
        total += s
        print(f"{name[:48]:48s} {s // 1024:6d} KB", flush=True)
    for x in ("so", "sn"):
        p = os.path.join(TMP, x)
        if os.path.exists(p):
            os.remove(p)
    print(f"총합 {total / 1048576:.2f} MB")


if __name__ == "__main__":
    main()
