"""
translation/translated/ 안의 korean 컬럼에 일본어 히라가나/가타카나가 실수로 남아있는지 검사.
여러 줄짜리(멀티라인) 항목에서 일부만 번역하고 나머지를 원문 그대로 두는 실수를 잡기 위한 것.
번역 작업 후 습관적으로 돌릴 것.
"""
import csv
import re
import glob
import os

PROJECT_ROOT = "/Users/sahncha/Projects/MindsBeneathUsKorean"
KANA = re.compile(r"[぀-ヿ]")


def check_file(path, key_field="key"):
    found = 0
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ko = row.get("korean", "")
            if ko.strip() and KANA.search(ko):
                found += 1
                ident = row.get(key_field) or row.get("node", "")
                print(f"  [{os.path.basename(path)}] {ident!r} -> {ko!r}")
    return found


def main():
    total = 0
    total += check_file(os.path.join(PROJECT_ROOT, "translation/translated/workbook.csv"), "key")
    for path in sorted(glob.glob(os.path.join(PROJECT_ROOT, "translation/translated/dialogue/*.csv"))):
        total += check_file(path, "node")

    print()
    if total == 0:
        print("이상 없음 — 가나 잔존 없음.")
    else:
        print(f"총 {total}건 발견 — 위 항목들 확인/수정할 것.")


if __name__ == "__main__":
    main()
