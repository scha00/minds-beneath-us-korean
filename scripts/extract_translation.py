import UnityPy
import csv
import os
import re

PROJECT_ROOT = "/Users/sahncha/Projects/MindsBeneathUsKorean"
# 원본 번들은 resource/ 에 로컬 캐시해둔 걸 씀 (SSD 안 꽂혀있어도 동작하게).
# resource/ 에 파일이 없으면: SSD($DATA/StreamingAssets/aa/StandaloneWindows64/)에서 다시 복사할 것.
BUNDLE_DIR = os.path.join(PROJECT_ROOT, "resource")
OUT_DIALOGUE = os.path.join(PROJECT_ROOT, "translation/dialogue")
OUT_WORKBOOK = os.path.join(PROJECT_ROOT, "translation/workbook")

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

WORKBOOK_BUNDLE = "globalset_assets_all_14f5b55c4c055b061135896f7409af81.bundle"
JP_INDEX = 3  # ReleasedLanguage.JapanJapanese


def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()


def extract_dialogue_bundle(bundle_filename, idx):
    path = os.path.join(BUNDLE_DIR, bundle_filename)
    env = UnityPy.load(path)

    ja_obj = None
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if tree.get("LanguageCode") == "ja-JP":
            ja_obj = tree
            break

    if ja_obj is None:
        print(f"  [경고] ja-JP 없음: {bundle_filename}")
        return 0, None

    chapter_name = ja_obj.get("m_Name", bundle_filename)
    chapter_name_clean = re.sub(r"\s*\(ja-JP\)\s*$", "", chapter_name)

    ref_map = {r["rid"]: r for r in ja_obj["references"]["RefIds"]}

    rows = []
    for node in ja_obj["Nodes"]:
        node_title = node.get("Title", "")
        for line in node.get("Lines", []):
            for unit_ref in line.get("Units", []):
                rid = unit_ref.get("rid")
                ref = ref_map.get(rid)
                if ref is None:
                    continue
                cls = ref["type"]["class"]
                data = ref["data"]
                if cls == "YarnSayUnit":
                    rows.append({
                        "bundle_file": bundle_filename,
                        "node": node_title,
                        "type": "Say",
                        "role": data.get("Role", ""),
                        "say_index": data.get("TranslationID", {}).get("sayIndex", ""),
                        "japanese": data.get("Line", ""),
                        "korean": "",
                    })
                elif cls == "YarnBranchUnit":
                    rows.append({
                        "bundle_file": bundle_filename,
                        "node": node_title,
                        "type": "Branch",
                        "role": "#Simple",
                        "say_index": data.get("TranslationID", {}).get("sayIndex", ""),
                        "japanese": data.get("Selection", ""),
                        "korean": "",
                    })

    fname = f"{idx:02d}_{sanitize_filename(chapter_name_clean)}.csv"
    out_path = os.path.join(OUT_DIALOGUE, fname)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["bundle_file", "node", "type", "role", "say_index", "japanese", "korean"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"  -> {fname}: {len(rows)}줄")
    return len(rows), out_path


def extract_workbook():
    path = os.path.join(BUNDLE_DIR, WORKBOOK_BUNDLE)
    env = UnityPy.load(path)

    wb = None
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if tree.get("m_Name") == "翻譯對照表":
            wb = tree
            break

    if wb is None:
        print("  [경고] Workbook을 못 찾음")
        return 0

    total = 0
    out_path = os.path.join(OUT_WORKBOOK, "workbook.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["sheet", "key", "japanese", "korean"])
        writer.writeheader()
        for sheet in wb["Sheets"]:
            title = sheet.get("Title", "")
            for row in sheet.get("Rows", []):
                key = row.get("key", "")
                datas = row.get("datas", [])
                ja = datas[JP_INDEX] if len(datas) > JP_INDEX else ""
                writer.writerow({"sheet": title, "key": key, "japanese": ja, "korean": ""})
                total += 1

    print(f"  -> workbook.csv: {total}행")
    return total


if __name__ == "__main__":
    print("=== 대사 추출 ===")
    total_lines = 0
    for i, b in enumerate(DIALOGUE_BUNDLES, start=1):
        print(f"[{i}/{len(DIALOGUE_BUNDLES)}] {b}")
        n, _ = extract_dialogue_bundle(b, i)
        total_lines += n

    print()
    print("=== 워크북 추출 ===")
    wb_rows = extract_workbook()

    print()
    print(f"총 대사/선택지 줄 수: {total_lines}")
    print(f"총 워크북 행 수: {wb_rows}")
