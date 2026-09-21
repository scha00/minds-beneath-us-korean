"""
Addressables 카탈로그에서 CRC 검사가 켜진 번들을 찾아 scripts/bundle_crc.json 으로 저장한다.

카탈로그(m_ExtraDataString)의 AssetBundleRequestOptions 에 m_Crc 가 0이 아닌 번들은, 게임이 로드할 때
"압축 푼 데이터 스트림의 CRC32"가 그 값과 다르면 로드를 거부한다(→ 씬이 멈춤). 현재 게임에는 딱 하나
(scene_finalerrortalk_scenes_all_08f3f0c3…, 엔딩 후 씬)가 해당한다. 이런 번들은 build_diff_patch.py 가
스트림에 4바이트를 덧붙여 CRC32 를 원본과 똑같이 맞춘다(CRC 위조). 카탈로그 자체는 수정하지 않는다.

    python3 scripts/extract_bundle_crc.py [catalog.json 경로]
"""
import base64
import json
import os
import re
import sys

DEFAULT = "/Volumes/Extreme SSD/mbu_data/MindsBeneathUs_Data/StreamingAssets/aa/catalog.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bundle_crc.json")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    cat = json.load(open(path, encoding="utf-8"))
    raw = base64.b64decode(cat["m_ExtraDataString"])
    s = re.sub(rb"\x00", b"", raw).decode("utf-8", "ignore")
    out = {}
    for m in re.finditer(r'"m_Hash":"([0-9a-f]{32})","m_Crc":(\d+)', s):
        if int(m.group(2)) != 0:
            out[m.group(1)] = int(m.group(2))
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"CRC 검사 번들 {len(out)}개 -> {OUT}: {out}")


if __name__ == "__main__":
    main()
