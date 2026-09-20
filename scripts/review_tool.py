"""
전체 대사 검토·수정 도구 (이름/호칭/말투를 문맥에 맞게 손보는 작업용).

review/*.jsonl 은 scripts/build_review_data.py 가 만든 줄 단위 4개 국어 정렬 데이터다.

    python3 scripts/review_tool.py files                      # 파일 목록/진행 상황
    python3 scripts/review_tool.py show 07 0 60               # 07번 파일 0~59번 줄 보기
    python3 scripts/review_tool.py apply fixes.tsv            # 수정 적용
    python3 scripts/review_tool.py mark 07 0 60               # 0~59번 줄 검토 완료 표시
    python3 scripts/review_tool.py find 07 "패턴"              # 한국어 칸 정규식 검색(보기용, 수정 X)

fixes.tsv 한 줄 = `파일접두사<TAB>줄번호<TAB>새 한국어`. 좌표(파일, 줄 번호)로만 고치므로 텍스트 검색
치환처럼 엉뚱한 줄을 건드릴 일이 없다. 02번 파일은 10번과 내용이 100% 같아서 10번을 고치면 02번에도
같은 줄 번호로 자동 복사한다.
"""
import csv
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(ROOT, "review")
DLG = os.path.join(ROOT, "translation", "translated", "dialogue")
WB = os.path.join(ROOT, "translation", "translated", "workbook.csv")
DONE = os.path.join(REVIEW, "done.json")
NARR = {"心の声", "システム", "「異常」"}


def review_files():
    return sorted(glob.glob(os.path.join(REVIEW, "*.jsonl")))


def find_review(prefix):
    m = [f for f in review_files() if os.path.basename(f).startswith(prefix)]
    if len(m) != 1:
        sys.exit(f"'{prefix}' 에 맞는 파일이 {len(m)}개: {[os.path.basename(x) for x in m]}")
    return m[0]


def load(prefix):
    with open(find_review(prefix), encoding="utf-8") as f:
        rows = [json.loads(l) for l in f]
    # ko 는 항상 현재 CSV 값을 따른다(수정 후에도 최신 상태로 보이게).
    csv_rows, _ = read_csv(find_csv(prefix))
    for r in rows:
        r["ko"] = csv_rows[r["i"] + 1][6]
    return rows


def speaker_names():
    """일본어 화자명 -> 지금 이름표(한국어)."""
    with open(WB, encoding="utf-8-sig", newline="") as f:
        return {r["japanese"]: r["korean"] for r in csv.DictReader(f) if r["sheet"] == "角色"}


def load_done():
    return json.load(open(DONE)) if os.path.exists(DONE) else {}


def cmd_files():
    done = load_done()
    for f in review_files():
        rows = sum(1 for _ in open(f, encoding="utf-8"))
        name = os.path.basename(f).replace(".jsonl", "")
        covered = sum(b - a for a, b in done.get(name[:2], []))
        print(f"{name}\t{rows}줄\t검토 {covered}줄")


def cmd_show(prefix, a, b):
    rows = load(prefix)
    names = speaker_names()
    last_other = {}
    prev = None
    # 상대(청자) 추정: 바로 앞에서 말한 다른 화자. 선택지(#Simple)는 주인공.
    for r in rows[:a]:
        if r["role"] not in NARR:
            prev = r["role"]
    hist = [prev]
    for r in rows[a:b]:
        role = r["role"]
        nm = "나(주인공)" if role == "#Simple" else names.get(role, role)
        if role in NARR:
            who = nm
        else:
            listener = next((h for h in reversed(hist) if h and h != role), None)
            ln = "나" if listener == "#Simple" else names.get(listener, listener or "?")
            who = f"{nm}→{ln}"
            hist.append(role)
        tag = "선" if r["type"] == "Branch" else " "
        print(f'{r["i"]}{tag}[{who}] {r["ko"]} ‖ {r["en"]} ‖ {r["ja"]}')


def find_csv(prefix):
    m = [f for f in glob.glob(os.path.join(DLG, "*.csv")) if os.path.basename(f).startswith(prefix)]
    if len(m) != 1:
        sys.exit(f"CSV '{prefix}' 후보 {len(m)}개")
    return m[0]


def read_csv(path):
    raw = open(path, "rb").read().decode("utf-8-sig")
    crlf = "\r\n" in raw
    rows = list(csv.reader(io.StringIO(raw, newline="")))
    return rows, crlf


def write_csv(path, rows, crlf):
    out = io.StringIO()
    csv.writer(out, lineterminator="\r\n" if crlf else "\n").writerows(rows)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(out.getvalue())


def cmd_apply(tsv):
    fixes = {}
    for ln, l in enumerate(open(tsv, encoding="utf-8"), 1):
        l = l.rstrip("\n")
        if not l.strip() or l.startswith("#"):
            continue
        p = l.split("\t")
        if len(p) != 3:
            sys.exit(f"{ln}번째 줄 형식 오류(탭 3칸 필요): {l[:60]}")
        fixes.setdefault(p[0], {})[int(p[1])] = p[2]
    total = 0
    for prefix, d in fixes.items():
        targets = [prefix]
        if prefix == "10":
            targets.append("02")
        for t in targets:
            path = find_csv(t)
            rows, crlf = read_csv(path)
            for i, ko in d.items():
                if i + 1 >= len(rows):
                    sys.exit(f"{t}번 파일에 {i}번 줄 없음")
                rows[i + 1][6] = ko
                total += 1
            write_csv(path, rows, crlf)
    print(f"{total}줄 수정 적용")


def cmd_mark(prefix, a, b):
    d = load_done()
    d.setdefault(prefix[:2], []).append([a, b])
    json.dump(d, open(DONE, "w"))


def cmd_find(prefix, pat):
    rx = re.compile(pat)
    for r in load(prefix):
        if rx.search(r["ko"]):
            print(f'{r["i"]}\t{r["role"]}\t{r["ko"]}')


if __name__ == "__main__":
    c = sys.argv[1:]
    if not c or c[0] == "files":
        cmd_files()
    elif c[0] == "show":
        cmd_show(c[1], int(c[2]), int(c[3]))
    elif c[0] == "apply":
        cmd_apply(c[1])
    elif c[0] == "mark":
        cmd_mark(c[1], int(c[2]), int(c[3]))
    elif c[0] == "find":
        cmd_find(c[1], c[2])
