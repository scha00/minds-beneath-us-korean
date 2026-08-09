"""
translation/translated/workbook.csv 의 korean 컬럼을 읽어서
Workbook(飜譯對照表) 에셋의 영어 슬롯(index 2, en-US)에 써넣고
globalset_assets_all 번들을 재조립한다.

japanese 컬럼은 번역 소스 참고용일 뿐이며, 실제로 덮어쓰는 대상은 항상 EN_INDEX(영어) 슬롯이다.
(일본어 슬롯은 절대 건드리지 않는다 — 타이틀 화면 폴백 안전장치 관련 결정사항, CLAUDE.md 참고)
"""
import UnityPy
import csv
import os

PROJECT_ROOT = "/Users/sahncha/Projects/MindsBeneathUsKorean"
BUNDLE_NAME = "globalset_assets_all_14f5b55c4c055b061135896f7409af81.bundle"
# 원본 번들은 resource/ 에 로컬 캐시해둔 걸 씀 (SSD 안 꽂혀있어도 빌드 가능하게).
# resource/ 에 파일이 없으면: SSD($DATA/StreamingAssets/aa/StandaloneWindows64/)에서 다시 복사할 것.
SRC = os.path.join(PROJECT_ROOT, "resource", BUNDLE_NAME)

TRANSLATED_CSV = os.path.join(PROJECT_ROOT, "translation/translated/workbook.csv")
OUT_DIR = os.path.join(PROJECT_ROOT, "install")
OUT_PATH = os.path.join(OUT_DIR, BUNDLE_NAME)

EN_INDEX = 2  # ReleasedLanguage.UnitedStateEnglish


def main():
    if not os.path.exists(SRC):
        raise FileNotFoundError(
            f"원본 번들 없음: {SRC}\n"
            f"resource/ 폴더가 비어있거나 이 파일이 빠진 것 — SSD 마운트해서 다시 복사할 것:\n"
            f"  cp \"/Volumes/Extreme SSD/mbu_data/MindsBeneathUs_Data/StreamingAssets/aa/StandaloneWindows64/{BUNDLE_NAME}\" "
            f"\"{os.path.dirname(SRC)}/\""
        )

    os.makedirs(OUT_DIR, exist_ok=True)

    translations = {}  # (sheet, key) -> korean text
    with open(TRANSLATED_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["korean"].strip():
                translations[(row["sheet"], row["key"])] = row["korean"]

    print(f"번역된 항목: {len(translations)}행")

    env = UnityPy.load(SRC)

    target_obj = None
    wb_tree = None
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if tree.get("m_Name") == "翻譯對照表":
            target_obj = obj
            wb_tree = tree
            break

    assert target_obj is not None, "Workbook(翻譯對照表)을 찾지 못함"

    patched_count = 0
    for sheet in wb_tree["Sheets"]:
        sheet_title = sheet["Title"]
        for row in sheet["Rows"]:
            key = (sheet_title, row["key"])
            if key in translations:
                row["datas"][EN_INDEX] = translations[key]
                patched_count += 1

    print(f"패치된 행: {patched_count} / {len(translations)}")

    target_obj.save_typetree(wb_tree)

    with open(OUT_PATH, "wb") as f:
        f.write(env.file.save(packer="lz4"))

    print(f"저장 완료: {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes)")


if __name__ == "__main__":
    main()
