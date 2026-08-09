"""
translation/translated/dialogue/*.csv 의 korean 컬럼을 읽어서
각 챕터 번들의 en-US YarnAsset에 대사를 써넣고 재조립한다.

- 매칭 방식: extract_translation.py 와 동일한 순서로 Nodes -> Lines -> Units 를 순회하면서
  나온 순서(행 순서)를 그대로 CSV 행과 1:1 매칭한다. (같은 챕터의 모든 언어는 노드/유닛 구조가 동일하다는
  전제 - 검증을 위해 개수가 안 맞으면 에러를 내고 중단한다.)
- YarnSayUnit: Line 필드만 교체 (Body는 런타임에 다시 읽히지 않는 원본 소스 토큰이라 안 건드림)
- YarnBranchUnit: Selection 필드만 교체 (Condition은 스크립트 변수 조건이라 절대 건드리면 안 됨)
- japanese 컬럼은 번역 소스 참고용일 뿐, 실제로 쓰는 슬롯은 항상 en-US (일본어 YarnAsset은 안 건드림)

한 번에 하나의 번들만 처리하고 싶으면 --bundle 인자로 파일명을 넘기면 된다.
기본은 DIALOGUE_BUNDLES 전체를 순회.
"""
import UnityPy
import csv
import os
import sys
import glob

PROJECT_ROOT = "/Users/sahncha/Projects/MindsBeneathUsKorean"
# 원본 번들은 resource/ 에 로컬 캐시해둔 걸 씀 (SSD 안 꽂혀있어도 빌드 가능하게).
# resource/ 에 파일이 없으면: SSD($DATA/StreamingAssets/aa/StandaloneWindows64/)에서 다시 복사할 것.
BUNDLE_DIR = os.path.join(PROJECT_ROOT, "resource")
TRANSLATED_DIR = os.path.join(PROJECT_ROOT, "translation/translated/dialogue")
OUT_DIR = os.path.join(PROJECT_ROOT, "install")

DIALOGUE_BUNDLES = [
    "scene_finalerrortalk_scenes_all_08f3f0c373758b208d1d446a3d2309d3.bundle",
    "scene_afterstory_scenes_finalerrortalk_walkthrough_3f07a05d6ca440ba1c1d435bd442c00e.bundle",
    "scene_demo_scenes_mbu_s1_mp1+2_t1_walkthrough_78aa0b103a7289282cf2c94f7343088b.bundle",
    "scene_demo_scenes_mbu_s0_sh_walkthrough_6dfb3bdc59755e008ecd3c5f76c94225.bundle",
    "16cb18d2a2b26981a5a165feae2e28bb.bundle",
    "d0e81a4acd55cfac60c2aa1bec155c08.bundle",
    "c56402ff2d4caa5bf2fe6bc1fb1eff21.bundle",
    "d30c62acdc62c5c962b5117bd28fb80c.bundle",
    "c93dee5141b63d08d3d8b0514cdfd4fb.bundle",
    "scene_afterstory_scenes_afterstory_logic_bd5151ed38e57b301ee0eee0ca697a9b.bundle",
    "ac41b849ea6253607bd63fccdf073614.bundle",
    "ea5a2e5b016740416bde3a3456c70e76.bundle",
    "5e03827b12d7ba437d60cedd39f08462.bundle",
    "c4f0ca6f4417db6f22428c1b717f0ae1.bundle",
    "fb6d4d4cc2d60bcc548ac4d95e2c4b1f.bundle",
    "7b045b2493718179159f5373a04bd670.bundle",
]

TARGET_LANG_CODE = "en-US"


def find_csv_for_bundle(bundle_filename):
    for path in glob.glob(os.path.join(TRANSLATED_DIR, "*.csv")):
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            first = next(reader, None)
            if first and first["bundle_file"] == bundle_filename:
                return path
    return None


def patch_bundle(bundle_filename):
    csv_path = find_csv_for_bundle(bundle_filename)
    if csv_path is None:
        print(f"  [건너뜀] 매칭되는 번역 CSV 없음: {bundle_filename}")
        return 0

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    translated_rows = [r for r in rows if r["korean"].strip()]
    if not translated_rows:
        print(f"  [건너뜀] 번역된 행 없음: {os.path.basename(csv_path)}")
        return 0

    path = os.path.join(BUNDLE_DIR, bundle_filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"원본 번들 없음: {path}\n"
            f"resource/ 폴더에 이 파일이 빠진 것 — SSD 마운트해서 다시 복사할 것:\n"
            f"  cp \"/Volumes/Extreme SSD/mbu_data/MindsBeneathUs_Data/StreamingAssets/aa/StandaloneWindows64/{bundle_filename}\" "
            f"\"{BUNDLE_DIR}/\""
        )
    env = UnityPy.load(path)

    target_obj = None
    target_tree = None
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if tree.get("LanguageCode") == TARGET_LANG_CODE:
            target_obj = obj
            target_tree = tree
            break

    assert target_obj is not None, f"{TARGET_LANG_CODE} YarnAsset을 못 찾음: {bundle_filename}"

    ref_map = {r["rid"]: r for r in target_tree["references"]["RefIds"]}

    # extract_translation.py 와 동일한 순서로 순회하며 (rid, class) 리스트를 만든다.
    ordered_units = []
    for node in target_tree["Nodes"]:
        for line in node.get("Lines", []):
            for unit_ref in line.get("Units", []):
                rid = unit_ref.get("rid")
                ref = ref_map.get(rid)
                if ref is None:
                    continue
                cls = ref["type"]["class"]
                if cls in ("YarnSayUnit", "YarnBranchUnit"):
                    ordered_units.append(ref)

    if len(ordered_units) != len(rows):
        print(f"  [경고] 구조 불일치! CSV 행수={len(rows)} vs en-US 유닛수={len(ordered_units)} : {bundle_filename}")
        print(f"         이 번들은 건너뜁니다. 수동 확인 필요.")
        return 0

    patched = 0
    for row, ref in zip(rows, ordered_units):
        ko = row["korean"].strip()
        if not ko:
            continue
        data = ref["data"]
        if ref["type"]["class"] == "YarnSayUnit":
            data["Line"] = ko
        elif ref["type"]["class"] == "YarnBranchUnit":
            data["Selection"] = ko
        patched += 1

    target_obj.save_typetree(target_tree)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, bundle_filename)
    with open(out_path, "wb") as f:
        f.write(env.file.save(packer="lz4"))

    print(f"  -> {bundle_filename}: {patched}줄 패치, 저장: {out_path}")
    return patched


def main():
    targets = DIALOGUE_BUNDLES
    if len(sys.argv) > 1 and sys.argv[1] == "--bundle":
        targets = [sys.argv[2]]

    total = 0
    for i, b in enumerate(targets, start=1):
        print(f"[{i}/{len(targets)}] {b}")
        total += patch_bundle(b)

    print()
    print(f"총 패치된 줄 수: {total}")


if __name__ == "__main__":
    main()
