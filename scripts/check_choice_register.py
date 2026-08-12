"""
같은 화면에 동시에 뜨는 선택지들끼리 반말/존댓말이 섞여 있는지 검사한다.

## 배경

`translation/translated/dialogue/*.csv`의 Branch(선택지) 행들은 그냥 한 줄로 쭉 나열되어
있어서, 어떤 선택지들이 실제로 게임 화면에서 "같이" 뜨는 하나의 선택지 묶음인지 CSV만
봐서는 알 수 없다. 원본 Yarn 노드 데이터에는 각 줄마다 `Indent`(들여쓰기 단계) 필드가
있는데, **같은 들여쓰기 단계에서 연속으로 나오는 YarnBranchUnit들이 실제로 한 화면에
같이 뜨는 선택지 묶음**이다(하나를 고르면 그 선택지의 몸통은 한 단계 더 깊은 들여쓰기로
들어가고, 다른 선택지들의 몸통을 다 건너뛴 뒤 다시 원래 단계로 합류하는 구조 — 표준적인
Yarn Spinner 숏컷 옵션(`->`) 문법).

이 스크립트는 그 Indent 정보를 이용해 실제 선택지 묶음을 재구성하고, 각 묶음 안에서
번역된 한국어 문장들의 종결어미가 반말/존댓말로 섞여 있으면 경고한다. (실제로 2026-08-12에
사용자가 스크린샷으로 발견한 "그쪽이 질문 공세를 하니까." / "제 버릇이라서요." 불일치가
바로 이 패턴 — 이후로 유사 사례가 더 있는지 전수 검사하기 위해 만듦.)

## 한계 (중요)

이건 어미 패턴 매칭 기반 휴리스틱이라 완벽하지 않다:
- "……"만 있거나 이름/감탄사만 있는 짧은 선택지는 판정 불가(neutral로 분류, 무시함)
- 반말/존댓말 여부가 명확한 어미만 잡아낸다 — 애매한 경우(예: 명사로 끝나는 문장)는 놓칠 수 있음
- **경고가 뜬다고 무조건 버그는 아니다** — 이번 세션에서 실제로 겪었듯, 화자가 당황하거나
  비꼬는 뉘앙스로 일부러 존댓말을 섞는 의도된 연출일 수도 있다(예: 셴 소가 정말로 다른
  언어로 말하는 경우, 또는 서로 다른 대상에게 하는 말이 한 그룹으로 잘못 묶인 경우 등).
  **반드시 사람이 직접 문맥을 확인하고 판단할 것** — 이 스크립트는 "의심되는 곳을 좁혀주는"
  용도지, 자동으로 고쳐주는 도구가 아니다.

## 사용법
    python3 scripts/check_choice_register.py                # 전체 스캔
    python3 scripts/check_choice_register.py --bundle <파일명>  # 번들 하나만
"""
import UnityPy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from patch_dialogue import (
    BUNDLE_DIR,
    DIALOGUE_BUNDLES,
    TARGET_LANG_CODE,
    build_signature_table,
    node_signature,
)

# 존댓말 종결(해요체/하십시오체 등) — "요"로 끝나거나 격식체 어미로 끝나는 경우.
POLITE_SUFFIXES = (
    "요", "죠", "세요", "셔요",
)
# "습니다"/"입니다"/"합니다"/"십니다"/"드립니다"(그리고 "~까" 의문형)를 한꺼번에 잡는 패턴.
# 단순히 "니다"로 끝나는지만 보면 "아니다"(반말 "~가 아니다") 같은 단어가 끝 두 글자만
# 우연히 "니다"와 같아서 존댓말로 오판된다. 하십시오체 "-ㅂ니다"는 어간 모음에 따라
# 붙는 음절이 제각각이라(됩니다/옵니다/드립니다/줍니다……) 음절을 일일이 나열할 수
# 없으므로, 한글 음절 분해로 "니다"/"니까" 바로 앞 글자의 받침이 ㅂ(또는 ㅄ)인지,
# 혹은 그 글자가 "습"/"십"(자음 어간용 삽입 음절)인지를 직접 검사한다.
def is_hasipsio_ending(t):
    if len(t) < 3 or t[-2:] not in ("니다", "니까"):
        return False
    prev = t[-3]
    if prev in ("습", "십"):
        return True
    code = ord(prev)
    if 0xAC00 <= code <= 0xD7A3:
        final_consonant = (code - 0xAC00) % 28
        return final_consonant in (17, 18)  # 17=ㅂ, 18=ㅄ 받침
    return False
# 반말 종결 — 순수 반말 어미로 끝나는 경우. "요"가 뒤에 안 붙은 경우만 해당하므로
# POLITE_SUFFIXES 체크를 먼저 하고 나서 이 목록을 본다.
CASUAL_SUFFIXES = (
    "다", "어", "아", "지", "냐", "니", "야", "라", "자", "게", "든",
    "잖아", "거든", "군", "네", "데", "구나", "고", "든지",
)


def classify_register(text):
    """반말/존댓말/판정불가 중 하나를 돌려준다."""
    t = text.strip().strip('"')
    # 말줄임표, 느낌표, 물음표, 따옴표 등 트레일링 기호 제거
    t = re.sub(r"[!?…\.\s]+$", "", t)
    if not t:
        return "neutral"
    # 너무 짧거나(이름/감탄사 등) 어미 패턴이 뚜렷하지 않은 경우는 판정하지 않음
    if len(t) < 2:
        return "neutral"

    if is_hasipsio_ending(t):
        return "polite"
    for suf in POLITE_SUFFIXES:
        if t.endswith(suf):
            return "polite"
    for suf in CASUAL_SUFFIXES:
        if t.endswith(suf):
            return "casual"
    return "neutral"


def collect_branch_groups(tree):
    """Nodes -> Lines 를 순회하면서, 실제로 한 화면에 동시에 뜨는 선택지 묶음을 재구성한다.

    Yarn 소스의 숏컷 옵션(`->`) 문법은 같은 들여쓰기(Indent)의 옵션 여러 개가 한 묶음이고,
    각 옵션을 고르면 그 몸통은 한 단계 더 깊은 들여쓰기로 들어갔다가 다시 원래 단계로
    돌아온다. 그런데 "같은 Indent"라는 조건만으로는 부족하다 — 완전히 무관한, 서로 다른
    시점의 선택지들도 결국 같은 기본 Indent(보통 0)에서 시작하기 때문에 그냥 이어붙이면
    안 관련된 선택지들까지 한 묶음으로 잘못 합쳐진다. 실제로 그렇게 되는 걸 확인했음.

    관찰해보니 각 숏컷 옵션 묶음은 시작 전/끝난 후에 그 Indent 그대로인 비-선택지 줄
    (보통 YarnControlUnit)이 하나씩 있다 — 즉 "같은 Indent의 비-선택지 줄을 만나면
    그 Indent에서 열려있던 묶음을 닫는다"는 규칙을 추가해야 진짜 경계가 잡힌다.

    각 그룹은 [(branch_index, selection_text), ...] 형태.
    branch_index는 그 노드 안에서 몇 번째 YarnBranchUnit인지(=CSV의 Branch 행 say_index와 동일)."""
    ref_map = {r["rid"]: r for r in tree["references"]["RefIds"]}
    all_groups = {}  # node_title -> list of groups

    for node in tree["Nodes"]:
        groups_here = []
        stack = []  # [(indent, group_list)]
        branch_index = 0

        for line in node.get("Lines", []):
            indent = line.get("Indent", 0)
            branch_units = []
            other_units = False
            for unit_ref in line.get("Units", []):
                ref = ref_map.get(unit_ref.get("rid"))
                if ref is None:
                    continue
                if ref["type"]["class"] == "YarnBranchUnit":
                    branch_units.append(ref)
                else:
                    other_units = True

            # 이 줄보다 깊은 들여쓰기에서 열려있던 묶음은 여기서 다 닫는다 (dedent).
            while stack and stack[-1][0] > indent:
                _, finished = stack.pop()
                if len(finished) >= 2:
                    groups_here.append(finished)

            if branch_units:
                entries = []
                for ref in branch_units:
                    idx = branch_index
                    branch_index += 1
                    entries.append((idx, ref["data"].get("Selection", "")))
                if stack and stack[-1][0] == indent:
                    stack[-1][1].extend(entries)
                else:
                    stack.append((indent, entries))
            elif other_units or line.get("Units"):
                # 선택지가 아닌 줄(주로 YarnControlUnit)이 같은 Indent에 나오면,
                # 그 Indent에서 열려있던 선택지 묶음은 여기서 끝난 것으로 본다.
                if stack and stack[-1][0] == indent:
                    _, finished = stack.pop()
                    if len(finished) >= 2:
                        groups_here.append(finished)

        while stack:
            _, finished = stack.pop()
            if len(finished) >= 2:
                groups_here.append(finished)

        if groups_here:
            all_groups[node["Title"]] = groups_here

    return all_groups


def main():
    targets = DIALOGUE_BUNDLES
    if len(sys.argv) > 2 and sys.argv[1] == "--bundle":
        targets = [sys.argv[2]]

    print("시그니처 테이블 구성 중...")
    signature_table = build_signature_table()
    print(f"  {len(signature_table)}개 씬 시그니처 등록됨\n")

    total_groups_checked = 0
    total_flagged = 0

    for bundle_filename in targets:
        path = os.path.join(BUNDLE_DIR, bundle_filename)
        if not os.path.exists(path):
            print(f"  [건너뜀] 원본 없음: {bundle_filename}")
            continue
        env = UnityPy.load(path)

        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            if tree.get("LanguageCode") != TARGET_LANG_CODE or "Nodes" not in tree:
                continue

            sig = node_signature(tree)
            entry = signature_table.get(sig)
            if entry is None:
                continue
            rows, csv_name = entry

            # (node, branch_index) -> korean text, Branch 행만
            lookup = {}
            counters = {}
            for row in rows:
                if row["type"] != "Branch":
                    continue
                key_node = row["node"]
                idx = counters.get(key_node, 0)
                counters[key_node] = idx + 1
                lookup[(key_node, idx)] = row["korean"].strip()

            groups_by_node = collect_branch_groups(tree)
            for node_title, groups in groups_by_node.items():
                for group in groups:
                    korean_texts = []
                    for idx, _jp_text in group:
                        ko = lookup.get((node_title, idx))
                        if ko:
                            korean_texts.append(ko)
                    if len(korean_texts) < 2:
                        continue
                    total_groups_checked += 1
                    classes = {classify_register(t) for t in korean_texts}
                    classes.discard("neutral")
                    if len(classes) >= 2:
                        total_flagged += 1
                        print(f"[의심] {csv_name} / 노드 '{node_title}'")
                        for t in korean_texts:
                            print(f"    ({classify_register(t)}) {t}")
                        print()

    print(f"총 {total_groups_checked}개 선택지 묶음 검사, {total_flagged}개 의심 사례 발견")


if __name__ == "__main__":
    main()
