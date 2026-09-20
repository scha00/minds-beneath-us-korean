"""
줄 단위 검토용 데이터 생성기.

번역 CSV(translation/translated/dialogue/*.csv)의 각 행에, 원본 번들에서 뽑은 중국어(zh-TW)와
영어(en-US) 원문을 같은 줄끼리 맞춰 붙인다. 이름/호칭 불일치나 말투(반말/존댓말) 불일치를
"한국어 칸 검색"이 아니라 "원문 대조"로 전수 검토하기 위한 자료다.

정렬 방식은 patch_dialogue.py와 동일하다: CSV 행 i = en-US YarnAsset의 i번째 (Say/Branch)
유닛, 그리고 노드 제목 시퀀스(시그니처)가 같은 zh-TW(dev) YarnAsset의 i번째 유닛.

출력: review/<CSV 파일명>.jsonl  (한 줄 = 한 행)
  {"i", "node", "type", "role", "idx", "zh", "en", "ja", "ko"}
review/ 는 .gitignore(deny-by-default)에 막혀있어 커밋되지 않는다(원문 텍스트 포함이라 공개 금지).

사용법:
    python3 scripts/build_review_data.py
"""
import json
import os
import sys

import UnityPy

sys.path.insert(0, os.path.dirname(__file__))
from patch_dialogue import (  # noqa: E402
    BUNDLE_DIR,
    DEV_LANG_CODE,
    TARGET_LANG_CODE,
    build_signature_table,
    collect_units,
    node_signature,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_ROOT, "review")


def unit_text(ref):
    data = ref["data"]
    if ref["type"]["class"] == "YarnSayUnit":
        return data.get("Line", "")
    return data.get("Selection", "")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("시그니처 테이블 구성 중...")
    table = build_signature_table()

    # 번들 파일명 -> [(en_tree, dev_trees)] 를 미리 모아둔다.
    by_bundle = {}
    for sig, (rows, csv_name) in table.items():
        by_bundle.setdefault(rows[0]["bundle_file"], []).append((sig, rows, csv_name))

    written = 0
    for bundle_filename, entries in by_bundle.items():
        env = UnityPy.load(os.path.join(BUNDLE_DIR, bundle_filename))
        en_by_sig, dev_trees = {}, []
        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            if "Nodes" not in tree or "LanguageCode" not in tree:
                continue
            if tree["LanguageCode"] == TARGET_LANG_CODE:
                en_by_sig.setdefault(node_signature(tree), tree)
            elif tree["LanguageCode"] == DEV_LANG_CODE:
                dev_trees.append(tree)

        for sig, rows, csv_name in entries:
            en_tree = en_by_sig.get(sig)
            if en_tree is None:
                print(f"  [경고] en-US 트리 못 찾음: {csv_name}")
                continue
            en_units = collect_units(en_tree)
            dev_tree = next((t for t in dev_trees if node_signature(t) == sig), None)
            if dev_tree is None:
                same = [t for t in dev_trees if len(collect_units(t)) == len(en_units)]
                dev_tree = same[0] if len(same) == 1 else None
            dev_units = collect_units(dev_tree) if dev_tree is not None else []
            if len(dev_units) != len(en_units):
                print(f"  [주의] zh 정렬 불가(개수 불일치), zh 비움: {csv_name}")
                dev_units = [None] * len(en_units)
            if len(en_units) != len(rows):
                print(f"  [경고] 행수 불일치, 건너뜀: {csv_name}")
                continue

            out_path = os.path.join(OUT_DIR, csv_name.replace(".csv", ".jsonl"))
            with open(out_path, "w", encoding="utf-8") as f:
                for i, (row, en_ref, dev_ref) in enumerate(zip(rows, en_units, dev_units)):
                    rec = {
                        "i": i,
                        "node": row["node"],
                        "type": row["type"],
                        "role": row["role"],
                        "idx": row["say_index"] if "say_index" in row else row.get("idx", ""),
                        "zh": unit_text(dev_ref) if dev_ref else "",
                        "en": unit_text(en_ref),
                        "ja": row["japanese"],
                        "ko": row["korean"],
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
            print(f"  저장: review/{os.path.basename(out_path)} ({len(rows)}행)")
    print(f"완료: {written}개 CSV")


if __name__ == "__main__":
    main()
