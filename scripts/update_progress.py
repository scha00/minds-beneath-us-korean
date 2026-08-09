"""
translation/translated/ 안의 CSV들을 스캔해서 progress.md 를 자동으로 다시 생성한다.
번역 작업 후에는 이 스크립트를 돌려서 진행 상황을 최신화할 것.

수동으로 progress.md를 고쳐쓰지 말 것 — 이 스크립트가 덮어씀.
"""
import csv
import os
import glob
import datetime

PROJECT_ROOT = "/Users/sahncha/Projects/MindsBeneathUsKorean"
WORKBOOK_CSV = os.path.join(PROJECT_ROOT, "translation/translated/workbook.csv")
DIALOGUE_DIR = os.path.join(PROJECT_ROOT, "translation/translated/dialogue")
OUT_PATH = os.path.join(PROJECT_ROOT, "progress.md")

# 其它 시트 안에서 원본 데이터가 깨져있어(값에 "(en-US)"가 그대로 붙어있는 등) 번역 대상에서
# 의도적으로 제외한 항목들. 여기 있으면 "미완료"로 안 세고 분모에서도 뺀다.
SKIP_KEYS = {
    "軌道顯示器校準者維持開機回到一般待機動畫動畫",
    "軌道顯示器待機動畫切到阿翰報告",
    "軌道顯示器最初始動畫",
}


def scan_workbook():
    sheets = {}  # title -> [total, done]
    with open(WORKBOOK_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["key"] in SKIP_KEYS:
                continue
            sheets.setdefault(row["sheet"], [0, 0])
            sheets[row["sheet"]][0] += 1
            if row["korean"].strip():
                sheets[row["sheet"]][1] += 1
    return sheets


def scan_dialogue():
    files = []  # (filename, total, done)
    for path in sorted(glob.glob(os.path.join(DIALOGUE_DIR, "*.csv"))):
        total = 0
        done = 0
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                if row["korean"].strip():
                    done += 1
        files.append((os.path.basename(path), total, done))
    return files


def bar(total, done, width=20):
    if total == 0:
        return "-" * width
    filled = round(width * done / total)
    return "#" * filled + "-" * (width - filled)


def main():
    sheets = scan_workbook()
    dialogue_files = scan_dialogue()

    wb_total = sum(t for t, _ in sheets.values())
    wb_done = sum(d for _, d in sheets.values())

    dlg_total = sum(t for _, t, _ in dialogue_files)
    dlg_done = sum(d for _, _, d in dialogue_files)

    grand_total = wb_total + dlg_total
    grand_done = wb_done + dlg_done

    lines = []
    lines.append("# 번역 진행 상황")
    lines.append("")
    lines.append(f"_자동 생성됨 ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}) — `scripts/update_progress.py` 실행 결과. 수동 편집 금지, 다시 실행하면 덮어씀._")
    lines.append("")
    lines.append(f"## 전체: {grand_done} / {grand_total} ({grand_done/grand_total*100:.1f}%)")
    lines.append("")
    lines.append(f"`{bar(grand_total, grand_done, 40)}`")
    lines.append("")

    lines.append("## Workbook (UI/퀘스트/아이템/캐릭터명 등)")
    lines.append("")
    lines.append(f"{wb_done} / {wb_total} ({wb_done/wb_total*100:.1f}%)")
    lines.append("")
    lines.append("| 시트 | 완료 | 전체 | 진행률 |")
    lines.append("|---|---:|---:|---|")
    # 원본 워크북 시트 순서 고정
    sheet_order = ["流程調查物件", "常態調查物件", "常態調查物件(工廠)", "互動", "任務", "角色", "章節", "其它", "人員名單"]
    for title in sheet_order:
        if title not in sheets:
            continue
        total, done = sheets[title]
        mark = " ✅" if done == total else ""
        lines.append(f"| {title}{mark} | {done} | {total} | `{bar(total, done)}` |")
    lines.append("")

    lines.append("## 대사 (YarnAsset, 챕터별)")
    lines.append("")
    lines.append(f"{dlg_done} / {dlg_total} ({dlg_done/dlg_total*100:.1f}%)")
    lines.append("")
    lines.append("| 챕터 파일 | 완료 | 전체 | 진행률 |")
    lines.append("|---|---:|---:|---|")
    for fname, total, done in dialogue_files:
        mark = " ✅" if done == total else ""
        short = fname.replace(".csv", "")
        lines.append(f"| {short}{mark} | {done} | {total} | `{bar(total, done)}` |")
    lines.append("")

    lines.append("## 참고")
    lines.append("")
    lines.append("- 이 파일은 `translation/translated/workbook.csv` 와 `translation/translated/dialogue/*.csv` 의")
    lines.append("  `korean` 컬럼이 채워진 행 수를 세서 만든다. 번역 작업 후 `python3 scripts/update_progress.py` 재실행할 것.")
    lines.append("- `02_yarn_後日談（240419）` 와 `10_yarn_後日談（240419）` 는 내용이 100% 동일한 중복 파일이다.")
    lines.append("  하나만 번역하고 다른 하나에 그대로 복사해도 된다 (재삽입은 둘 다 해야 함, CLAUDE.md 참고).")
    lines.append("- `其它` 시트의 일부 항목(3개)은 원본 데이터 자체가 깨져있어 번역 대상에서 제외함 (SKIP_KEYS, 이 스크립트 상단 참고).")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"저장 완료: {OUT_PATH}")
    print(f"전체 진행률: {grand_done} / {grand_total} ({grand_done/grand_total*100:.1f}%)")


if __name__ == "__main__":
    main()
