"""
translation/translated/dialogue/*.csv 의 korean 컬럼을 읽어서
각 챕터 번들의 en-US YarnAsset에 대사를 써넣고 재조립한다.

- 매칭 방식: extract_translation.py 와 동일한 순서로 Nodes -> Lines -> Units 를 순회하면서
  나온 순서(행 순서)를 그대로 CSV 행과 1:1 매칭한다. (같은 챕터의 모든 언어는 노드/유닛 구조가 동일하다는
  전제 - 검증을 위해 개수가 안 맞으면 에러를 내고 중단한다.)
- YarnSayUnit: Line 필드 교체 (Body는 런타임에 다시 읽히지 않는 원본 소스 토큰이라 안 건드림)
- YarnBranchUnit: Selection 필드만 교체 (Condition은 스크립트 변수 조건이라 절대 건드리면 안 됨)
- japanese 컬럼은 번역 소스 참고용일 뿐, 실제로 쓰는 슬롯은 항상 en-US (일본어 YarnAsset은 안 건드림)

## Role / TranslationID.characterName 교정 (중요 — 실제 플레이 중 발견된 버그의 수정)

게임 엔진(Creation.Yarn.Playing)은 대사를 표시할 때 이런 순서로 동작한다:
1. 원본(중국어, LanguageCode="") 유닛의 `Role`(예: "蔡明翰")을 키로 Workbook "角色" 시트에서
   목표 언어(en-US) 번역명을 찾는다 (예: "밍차이").
2. en-US YarnAsset 안에서, 각 유닛이 가진 `TranslationID.characterName`이 그 번역명("밍차이")과
   **똑같은** Say 유닛을 찾아서 그걸 재생한다 (`YarnAssetCollection.TryGetTranslation` →
   `YarnAsset.TryGetTranslatedUnit`, `TranslationIDInfo.Equals`가 `nodeName`+`characterName`+
   `sayIndex` 세 개를 전부 비교).

**핵심 함정**: `TranslationID`는 `Role`과는 별개로 직렬화된 필드다. `YarnSayUnit.ParseTranslation()`이
원본 yarn 스크립트를 최초로 컴파일할 때 `TranslationID.characterName = TranslationRole (= Role)`로
한 번 "굳혀서" 저장해두는 방식이라, 이후 `Role` 필드 값만 바꿔도 `TranslationID.characterName`은
자동으로 따라오지 않는다 — 완전히 독립된 값으로 남는다.

처음엔 `Role`만 en-US 원본 값(예: "Albert Tsai")에서 번역명("밍차이")으로 고쳤는데, 이것만으로는
안 됐다: `TranslationID.characterName`이 여전히 "Albert Tsai"로 남아있어서 위 1번에서 찾은
번역명("밍차이")과 매칭에 실패 → 게임이 통째로 원본(중국어) 유닛으로 폴백해버렸다 (Line도 Role도
전부 원본 중국어로 보임 — 화면에 표시되는 `Role` 텍스트를 고쳤는데도 매칭 자체는 여전히 실패하는,
겉으로는 "패치가 씹히는" 것처럼 보이는 증상이었다). `#Simple`(주인공 대사/선택지)의
`TranslationID.characterName`은 항상 상수 `"#Simple"`이라 이 이름 매칭 단계 자체를 타지 않기
때문에(`TranslationIDInfo.IsSimple`) 처음부터 정상 동작했던 것.

해결책: en-US YarnAsset의 각 YarnSayUnit마다, 같은 위치의 원본(zh-TW) 유닛 Role을 키로 Workbook
角色 시트에서 찾은 한글 번역명을 **`Role`(화면 표시용)과 `TranslationID.characterName`(매칭용) 둘
다에** 똑같이 써넣는다. 하나라도 빠지면 이 버그가 재발한다. (`#Simple`은 특수 마커라 번역 대상이
아니므로 그대로 둠.)

## 번들 하나에 같은 씬(scene)의 YarnAsset이 여러 벌 들어있는 경우

Addressables 패키징 때문에, 같은 씬의 YarnAsset(같은 Node 구성)이 여러 물리 .bundle 파일에 중복으로
박혀 있는 경우가 있다 (예: 教學關(튜토리얼)이 자기 전용 번들 말고도 다른 번들 안에 통째로 한 번 더 들어있음).
어느 사본이 실제로 게임에서 로드되는지 확신할 수 없으므로, 안전하게 "발견되는 모든 사본"을 전부 패치한다 —
Node 제목 목록(시그니처)으로 어느 CSV가 그 사본에 해당하는지 식별한다.

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
WORKBOOK_CSV = os.path.join(PROJECT_ROOT, "translation/translated/workbook.csv")
OUT_DIR = os.path.join(PROJECT_ROOT, "install")
DEV_LANG_CODE = ""  # zh-TW, 원본/개발 언어 슬롯

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
    # 2026-08-11 전수 스캔으로 새로 발견 (18~20번 CSV 원본). 상세 경위는 CLAUDE.md 참고.
    "scene_day3_scenes_fab_day3_logic_6346ee10c065ccc051a489a1ecff7695.bundle",
    "scene_sv_scenes_mbu_s1_sv_logic_c211782c0a3a66a35be6aceaf340b94e.bundle",
]

TARGET_LANG_CODE = "en-US"


def load_role_name_map():
    """Workbook 角色 시트: 중국어 원본 이름(key) -> 한글 번역명(korean)."""
    mapping = {}
    with open(WORKBOOK_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["sheet"] != "角色":
                continue
            ko = row["korean"].strip()
            if ko:
                mapping[row["key"]] = ko
    return mapping


ROLE_NAME_MAP = load_role_name_map()


def collect_units(tree):
    """Nodes -> Lines -> Units 순서로 (YarnSayUnit/YarnBranchUnit) ref 리스트를 만든다."""
    ref_map = {r["rid"]: r for r in tree["references"]["RefIds"]}
    ordered = []
    for node in tree["Nodes"]:
        for line in node.get("Lines", []):
            for unit_ref in line.get("Units", []):
                rid = unit_ref.get("rid")
                ref = ref_map.get(rid)
                if ref is None:
                    continue
                cls = ref["type"]["class"]
                if cls in ("YarnSayUnit", "YarnBranchUnit"):
                    ordered.append(ref)
    return ordered


def node_signature(tree):
    return tuple(n["Title"] for n in tree["Nodes"])


def csv_node_titles(rows):
    """CSV의 node 컬럼에서, 처음 등장한 순서대로 고유 노드 제목 목록을 뽑는다.
    (CSV에는 번역 대상 유닛이 없는 빈 노드는 안 나오므로, 이건 완전한 Node 시그니처의
    부분집합/부분수열이다 - 그래도 en-US 쪽 후보를 후보군으로 좁히는 데는 충분하다.)"""
    seen = []
    seen_set = set()
    for r in rows:
        n = r["node"]
        if n not in seen_set:
            seen_set.add(n)
            seen.append(n)
    return seen


def build_signature_table():
    """translation/translated/dialogue/ 안의 모든 CSV를 훑어서, 각 CSV가 실제로 어느
    en-US YarnAsset(Node 제목 시퀀스)에 해당하는지 찾아 시그니처 -> (rows, csv 파일명) 테이블을 만든다.

    한 물리 .bundle 파일 안에 여러 씬의 YarnAsset이 같이 들어있을 수 있어서(예: 05번 파일과
    17번 파일이 같은 번들 안에 같이 있음), bundle_file 컬럼만으로는 어떤 CSV가 어떤 씬인지
    특정할 수 없다. 그래서 후보(같은 bundle_file을 쓰는 en-US 오브젝트들) 중에서
    (a) 번역 대상 유닛 개수가 CSV 행수와 일치하고, (b) 후보의 Node 제목 목록이 CSV의 node
    컬럼에 나온 노드들을 전부 포함하는지를 보고 짝을 찾는다.
    """
    table = {}
    bundle_cache = {}  # bundle_filename -> list[(tree, unit_count, node_titles_set)]

    for csv_path in sorted(glob.glob(os.path.join(TRANSLATED_DIR, "*.csv"))):
        with open(csv_path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if not rows or not any(r["korean"].strip() for r in rows):
            continue
        bundle_filename = rows[0]["bundle_file"]

        if bundle_filename not in bundle_cache:
            candidates = []
            path = os.path.join(BUNDLE_DIR, bundle_filename)
            env = UnityPy.load(path)
            for obj in env.objects:
                if obj.type.name != "MonoBehaviour":
                    continue
                try:
                    tree = obj.read_typetree()
                except Exception:
                    continue
                if tree.get("LanguageCode") == TARGET_LANG_CODE and "Nodes" in tree:
                    candidates.append((tree, len(collect_units(tree)), set(node_signature(tree))))
            bundle_cache[bundle_filename] = candidates

        candidates = bundle_cache[bundle_filename]
        wanted_nodes = set(csv_node_titles(rows))
        matches = [
            tree for tree, unit_count, node_titles in candidates
            if unit_count == len(rows) and wanted_nodes <= node_titles
        ]
        if len(matches) != 1:
            print(f"  [경고] {os.path.basename(csv_path)} <-> {bundle_filename} 매칭 실패 (후보 {len(matches)}개) — 건너뜀")
            continue

        sig = node_signature(matches[0])
        table[sig] = (rows, os.path.basename(csv_path))
    return table


def patch_bundle(bundle_filename, signature_table):
    path = os.path.join(BUNDLE_DIR, bundle_filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"원본 번들 없음: {path}\n"
            f"resource/ 폴더에 이 파일이 빠진 것 — SSD 마운트해서 다시 복사할 것:\n"
            f"  cp \"/Volumes/Extreme SSD/mbu_data/MindsBeneathUs_Data/StreamingAssets/aa/StandaloneWindows64/{bundle_filename}\" "
            f"\"{BUNDLE_DIR}/\""
        )
    env = UnityPy.load(path)

    # 이 번들 안의 en-US YarnAsset을 전부 모으고 (중복 사본 포함), 원본(zh-TW) 후보도 전부 모은다.
    en_objs = []
    dev_candidates = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if "Nodes" not in tree or "LanguageCode" not in tree:
            continue
        if tree.get("LanguageCode") == TARGET_LANG_CODE:
            en_objs.append((obj, tree))
        elif tree.get("LanguageCode") == DEV_LANG_CODE:
            dev_candidates.append(tree)

    if not en_objs:
        print(f"  [건너뜀] en-US YarnAsset 없음: {bundle_filename}")
        return 0

    total_patched = 0
    total_role_fixed = 0
    role_missing = set()
    matched_any = False

    for target_obj, target_tree in en_objs:
        sig = node_signature(target_tree)
        entry = signature_table.get(sig)
        if entry is None:
            continue  # 이 시그니처에 해당하는 번역 CSV 없음(=번역 대상 아닌 씬) - 건드리지 않음
        matched_any = True
        rows, home_bundle = entry

        ordered_units = collect_units(target_tree)
        if len(ordered_units) != len(rows):
            print(f"  [경고] 구조 불일치! CSV 행수={len(rows)} vs en-US 유닛수={len(ordered_units)} : {bundle_filename} (원 소속: {home_bundle})")
            continue

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
        total_patched += patched

        # Role 필드 교정: 같은 시그니처를 가진 원본(zh-TW) 후보를 찾아 1:1 대조.
        dev_tree = None
        for cand in dev_candidates:
            if node_signature(cand) == sig:
                dev_tree = cand
                break
        if dev_tree is None:
            # 시그니처가 정확히 안 맞는 경우가 있다 (예: 19번/20번 CSV 소속 번들에서
            # en-US 쪽에만 빈 노드 "終止對話"가 하나 더 있어서 dev 쪽 Node 목록과 개수가
            # 1개 어긋남 — 실제로 겪은 케이스, 원본 게임 데이터 자체의 언어별 비대칭).
            # 이럴 때 Role 교정을 그냥 건너뛰면 그 씬 전체가 매칭 실패로 중국어 원문
            # 폴백되는 원래 버그가 재발하므로, 폴백으로 "유닛 개수가 유일하게 일치하는
            # 후보"를 찾아 대신 쓴다 (같은 번들 안의 다른 씬과 개수가 겹치지 않는 한 안전).
            same_count = [cand for cand in dev_candidates if len(collect_units(cand)) == len(ordered_units)]
            if len(same_count) == 1:
                dev_tree = same_count[0]
                print(f"  [주의] 시그니처 불일치, 유닛 개수({len(ordered_units)})로 대체 매칭: {bundle_filename} (시그니처 소속: {home_bundle})")
            else:
                print(f"  [경고] 원본(zh-TW) 짝을 못 찾음, Role 교정 건너뜀: {bundle_filename} (시그니처 소속: {home_bundle})")

        if dev_tree is not None:
            dev_units = collect_units(dev_tree)
            if len(dev_units) == len(ordered_units):
                for dev_ref, en_ref in zip(dev_units, ordered_units):
                    if en_ref["type"]["class"] != "YarnSayUnit":
                        continue
                    dev_role = dev_ref["data"].get("Role", "")
                    if not dev_role or dev_role == "#Simple":
                        continue
                    ko_name = ROLE_NAME_MAP.get(dev_role)
                    if ko_name is None:
                        role_missing.add(dev_role)
                        continue
                    changed = False
                    if en_ref["data"].get("Role") != ko_name:
                        en_ref["data"]["Role"] = ko_name
                        changed = True
                    # TranslationID.characterName은 Role과 별개로 직렬화된 필드라, 이것도
                    # 같이 안 맞춰주면 게임의 TryGetTranslatedUnit 매칭(TranslationID 전체
                    # 일치 비교)이 실패해서 화면엔 원본(중국어)으로 폴백된다 — 실제로 겪은 버그,
                    # Role만 고쳤을 때 이 필드를 놓쳐서 재발함. 반드시 같이 고칠 것.
                    translation_id = en_ref["data"].get("TranslationID")
                    if translation_id is not None and translation_id.get("characterName") != ko_name:
                        translation_id["characterName"] = ko_name
                        changed = True
                    if changed:
                        total_role_fixed += 1
            else:
                print(f"  [경고] 원본 유닛수({len(dev_units)}) != en-US 유닛수({len(ordered_units)}), Role 교정 건너뜀: {bundle_filename}")

        target_obj.save_typetree(target_tree)

    if role_missing:
        print(f"  [주의] Workbook 角色 시트에 없는 Role {len(role_missing)}개 (교정 못함): {sorted(role_missing)[:10]}{'...' if len(role_missing) > 10 else ''}")

    if not matched_any:
        print(f"  [건너뜀] 매칭되는 번역 CSV 없음: {bundle_filename}")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, bundle_filename)
    with open(out_path, "wb") as f:
        f.write(env.file.save(packer="lz4"))

    print(f"  -> {bundle_filename}: {total_patched}줄 패치, Role {total_role_fixed}개 교정, 저장: {out_path}")
    return total_patched


def main():
    targets = DIALOGUE_BUNDLES
    if len(sys.argv) > 1 and sys.argv[1] == "--bundle":
        targets = [sys.argv[2]]

    print("시그니처 테이블 구성 중...")
    signature_table = build_signature_table()
    print(f"  {len(signature_table)}개 씬 시그니처 등록됨")
    print()

    total = 0
    for i, b in enumerate(targets, start=1):
        print(f"[{i}/{len(targets)}] {b}")
        total += patch_bundle(b, signature_table)

    print()
    print(f"총 패치된 줄 수: {total}")


if __name__ == "__main__":
    main()
