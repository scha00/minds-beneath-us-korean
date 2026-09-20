"""
게임 본체 데이터 파일(TypeTree 없는 Unity 직렬화 파일) 패치 — 타이틀 화면용.

타이틀(시작) 화면이 원문 고정으로 나오던 이유: 타이틀 씬(level0)은 Addressables 의 Workbook 이 아니라
sharedassets0.assets 안에 들어있는 Workbook("翻譯對照表", path_id 1347) 복사본을 쓴다. 그래서 번들의
Workbook 만 한글로 바꿔서는 타이틀 메뉴가 안 바뀐다. 이 스크립트가 하는 일:
  1) sharedassets0.assets 의 Workbook 복사본에서 영어 슬롯(index 2)을 translated/workbook.csv 의 한글로 교체
  2) level0 의 하드코딩 영어 문구("This story is purely fictional…", path_id 3236)를 한글로 교체

.exe/.dll 은 건드리지 않는다. 결과는 install/player/ 아래에 만들어지고(로컬 임시물, 커밋 금지),
build_diff_patch.py 가 원본과의 diff 로 바꿔 배포한다.

    python3 scripts/patch_player_data.py
"""
import csv
import os
import struct
import sys

import UnityPy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT, "resource", "player")
SSD_DIR = "/Volumes/Extreme SSD/mbu_data/MindsBeneathUs_Data"
OUT_DIR = os.path.join(ROOT, "install", "player")
TRANSLATED_CSV = os.path.join(ROOT, "translation", "translated", "workbook.csv")
EN_INDEX = 2

WB_PATH_ID = 1347
DISCLAIMER_PATH_ID = 3236
DISCLAIMER_OLD = ("This story is purely fictional and is not related to any real people or events.\n"
                  "Any resemblance is purely coincidental.").encode("utf-8")
DISCLAIMER_NEW = ("이 이야기는 순수한 허구이며, 실제 인물이나 사건과는 무관합니다.\n"
                  "우연히 비슷한 점이 있더라도 순전히 우연입니다.").encode("utf-8")


def src_path(name):
    p = os.path.join(SRC_DIR, name)
    return p if os.path.exists(p) else os.path.join(SSD_DIR, name)


# ---- Unity 직렬화 기본형 (문자열: int32 길이 + 바이트 + 4바이트 정렬) ----
class Rd:
    def __init__(self, b):
        self.b, self.p = b, 0

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.p)[0]
        self.p += 4
        return v

    def s(self):
        n = self.i32()
        v = self.b[self.p:self.p + n].decode("utf-8")
        self.p += n
        self.p = (self.p + 3) & ~3
        return v

    def raw(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v


def w_str(s):
    b = s.encode("utf-8")
    out = struct.pack("<i", len(b)) + b
    return out + b"\0" * ((4 - len(out) % 4) % 4)


def parse_workbook(raw):
    r = Rd(raw)
    head = r.raw(28)              # m_GameObject(12) + m_Enabled(4) + m_Script(12)
    name = r.s()
    excel = r.raw(12)             # Excel (PPtr)
    sheets = []
    for _ in range(r.i32()):
        expanded = r.raw(4)       # bool + 정렬
        title = r.s()
        rows = []
        for _ in range(r.i32()):
            index = r.i32()
            key = r.s()
            datas = [r.s() for _ in range(r.i32())]
            rows.append([index, key, datas])
        sheets.append([expanded, title, rows])
    tail = raw[r.p:]
    return head, name, excel, sheets, tail


def build_workbook(head, name, excel, sheets, tail):
    out = bytearray(head) + w_str(name) + excel + struct.pack("<i", len(sheets))
    for expanded, title, rows in sheets:
        out += expanded + w_str(title) + struct.pack("<i", len(rows))
        for index, key, datas in rows:
            out += struct.pack("<i", index) + w_str(key) + struct.pack("<i", len(datas))
            for d in datas:
                out += w_str(d)
    return bytes(out) + tail


def save_serialized(env, path):
    sf = next(iter(env.files.values()))
    data = sf.save()
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tr = {}
    with open(TRANSLATED_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["korean"].strip():
                tr[(row["sheet"], row["key"])] = row["korean"]

    # 1) sharedassets0.assets 의 Workbook 복사본
    env = UnityPy.load(src_path("sharedassets0.assets"))
    obj = next(o for o in env.objects if o.path_id == WB_PATH_ID)
    raw = obj.get_raw_data()
    parsed = parse_workbook(raw)
    assert build_workbook(*parsed) == raw, "Workbook 파싱/재직렬화가 원본과 다름"
    head, name, excel, sheets, tail = parsed
    n = 0
    for _, title, rows in sheets:
        for row in rows:
            k = (title, row[1])
            if k in tr and len(row[2]) > EN_INDEX:
                row[2][EN_INDEX] = tr[k]
                n += 1
    print(f"sharedassets0.assets Workbook: {n}/{len(tr)}행 패치")
    obj.set_raw_data(build_workbook(head, name, excel, sheets, tail))
    print("  저장", save_serialized(env, os.path.join(OUT_DIR, "sharedassets0.assets")), "bytes")

    # 2) level0 의 하드코딩 영어 문구
    env = UnityPy.load(src_path("level0"))
    obj = next(o for o in env.objects if o.path_id == DISCLAIMER_PATH_ID)
    raw = obj.get_raw_data()
    assert raw.count(DISCLAIMER_OLD) == 1, "level0 원문 문자열을 못 찾음(게임 버전이 다를 수 있음)"
    i = raw.index(DISCLAIMER_OLD)
    assert struct.unpack("<i", raw[i - 4:i])[0] == len(DISCLAIMER_OLD)
    assert set(raw[i + len(DISCLAIMER_OLD):]) <= {0}
    body = raw[:i - 4] + struct.pack("<i", len(DISCLAIMER_NEW)) + DISCLAIMER_NEW
    body += b"\0" * ((4 - len(body) % 4) % 4)
    obj.set_raw_data(body)
    print("level0: 저장", save_serialized(env, os.path.join(OUT_DIR, "level0")), "bytes")


if __name__ == "__main__":
    main()
