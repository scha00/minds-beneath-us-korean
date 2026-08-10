"""
translation/translated/workbook.csv 의 角色(캐릭터) 시트를 읽어서
translation/character-keys.md 를 생성한다.

용도: 게임의 대사 번역 조회 시스템(YarnAssetCollection.TryGetTranslation)은
대사 화자 이름을 매칭할 때, 시작 언어(繁體中文/dev)판 YarnSayUnit의 Role 값
그대로를 "키"로 써서 Workbook 角色 시트를 조회하고, 그 결과로 나온 번역판
캐릭터명 문자열이 en-US(패치 슬롯) YarnAsset 안의 **`TranslationID.characterName`**
필드와 글자 그대로 일치해야만 정상적으로 번역된 대사가 뜬다 (일치하지 않으면
조용히 원문 中文으로 폴백됨 — 이 프로젝트에서 실제로 겪은 버그).

**주의**: 화면에 표시되는 화자 이름은 `Role` 필드이지만, 매칭에 쓰이는 건
`Role`과는 별개로 직렬화된 `TranslationID.characterName` 필드다. `Role`만
번역해서는 매칭이 안 되고(실제로 이 프로젝트에서 한 번 이렇게 잘못 배포한
적 있음 — CLAUDE.md의 "Role/TranslationID 버그" 참고), 둘 다 똑같이 번역명으로
맞춰야 한다.

즉 이 표의 "원본 키(繁體中文)" 컬럼이 대사 시스템 내부에서 캐릭터를 식별하는
진짜 키이고, 나머지는 언어별 표시용 이름일 뿐이다. 다른 언어로 패치를
만들려는 사람이라면 이 매핑을 그대로 참고해서 자기 언어 YarnAsset의 `Role`과
`TranslationID.characterName` 둘 다를 채워야 같은 버그를 피할 수 있다.

수동으로 고쳐쓰지 말 것 — 이 스크립트가 덮어씀. 번역 후 다시 실행할 것.
"""
import csv
import os

PROJECT_ROOT = "/Users/sahncha/Projects/MindsBeneathUsKorean"
WORKBOOK_CSV = os.path.join(PROJECT_ROOT, "translation/translated/workbook.csv")
OUT_PATH = os.path.join(PROJECT_ROOT, "translation/character-keys.md")


def main():
    rows = []
    with open(WORKBOOK_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["sheet"] != "角色":
                continue
            rows.append(row)

    total = len(rows)
    done = sum(1 for r in rows if r["korean"].strip())

    lines = []
    lines.append("# 캐릭터 이름 키 대응표")
    lines.append("")
    lines.append(
        "_자동 생성됨 — `scripts/export_character_keys.py` 실행 결과. "
        "수동 편집 금지, 다시 실행하면 덮어씀._"
    )
    lines.append("")
    lines.append(
        "이 게임(Minds Beneath Us)의 대사 번역 조회 시스템은 캐릭터 이름을 "
        "**繁體中文(원본 개발 언어) 표기 그대로**를 내부 키로 써서 다른 언어의 "
        "번역을 찾는다. 구체적으로:"
    )
    lines.append("")
    lines.append(
        "1. 대사 유닛(`YarnSayUnit`)에는 화자 이름을 담은 필드가 **두 개** 있다: "
        "화면 표시용 `Role`과, 매칭 전용으로 별도 직렬화된 `TranslationID.characterName`. "
        "**dev/繁體中文판 오브젝트의 Role 값**이 곧 그 캐릭터의 \"키\"가 된다."
    )
    lines.append(
        "2. 이 키로 Workbook의 `角色` 시트를 찾아 원하는 언어(예: 한국어를 "
        "덮어쓴 en-US 슬롯)의 번역된 캐릭터명을 얻는다."
    )
    lines.append(
        "3. 그 번역된 이름 문자열이 **해당 언어 YarnAsset 자신의 "
        "`TranslationID.characterName`**(⚠️`Role`이 아니다)과 글자 그대로 "
        "일치해야만 그 언어의 대사가 정상적으로 매칭된다. 일치하지 않으면 "
        "조용히 원본 繁體中文 대사로 폴백된다 — 즉 번역이 있어도 안 나오고 "
        "원문 중국어가 튀어나온다."
    )
    lines.append("")
    lines.append(
        "이 프로젝트에서 실제로 이 문제를 두 단계로 겪었다: 처음엔 `Role`만 "
        "번역명으로 고치면 되는 줄 알고 배포했는데도 여전히 중국어가 나왔다. "
        "원인은 `TranslationID.characterName`이 `Role`과 완전히 별개로 "
        "직렬화된 필드라서, `Role`만 바꿔도 원본 영문 placeholder 값 그대로 "
        "남아있었기 때문이었다. `scripts/patch_dialogue.py`는 이제 `Role`과 "
        "`TranslationID.characterName` **둘 다** 함께 교정한다."
    )
    lines.append("")
    lines.append(
        "**다른 언어로 이 게임을 패치하려는 사람은 아래 표의 \"원본 키"
        "(繁體中文)\" 컬럼을 그대로 키로 써서, 자기 언어 YarnAsset의 `Role`과 "
        "`TranslationID.characterName` 둘 다에 자기 언어로 번역한 이름을 "
        "채워 넣어야 한다. 하나만 고치면 매칭이 실패한다.**"
    )
    lines.append("")
    lines.append(f"총 {total}개 캐릭터 키 (한국어 번역 완료: {done}/{total})")
    lines.append("")
    lines.append("| 원본 키 (繁體中文) | 일본어 표기 (번역 참고 소스) | 한국어 번역 |")
    lines.append("|---|---|---|")
    for row in rows:
        key = row["key"]
        ja = row["japanese"]
        ko = row["korean"]
        lines.append(f"| {key} | {ja} | {ko} |")
    lines.append("")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"저장 완료: {OUT_PATH}")
    print(f"캐릭터 키 {total}개 (번역 완료 {done}개)")


if __name__ == "__main__":
    main()
