"""
UnityFS 번들 읽기/쓰기 최소 구현 (diff 패치 방식 전용).

diff 패치는 "번들 파일"이 아니라 "압축을 푼 데이터 스트림"끼리 비교한다. lz4 압축된 채로 비교하면
텍스트를 조금만 바꿔도 뒤쪽 압축 블록이 전부 달라져 diff가 부풀기 때문(19개 합계 121MB → 압축 풀고
비교하면 약 2MB).

사용자 PC의 install.ps1 도 이 파일과 똑같은 절차를 C#(Add-Type)으로 수행한다:
    원본 번들 -> (헤더/블록 정보 파싱, 블록별 lz4 해제) -> 데이터 스트림
    데이터 스트림 + xdelta 패치 -> 새 데이터 스트림
    새 데이터 스트림 -> 128KB 단위 lz4 압축 + 헤더/블록 정보 -> 새 번들

새 번들 레이아웃은 UnityPy가 save(packer="lz4")로 쓰던 것과 같다(이미 인게임 테스트 통과한 형식):
    헤더 flags=194(0xC2: lz4 + 블록정보 파일 끝 + 디렉터리 결합), 블록 flags=2(lz4), 블록 크기 128KB.
"""
import struct

import lz4.block

CHUNK = 0x20000
NEW_DATA_FLAGS = 194
NEW_BLOCK_FLAGS = 2


def _cstr(buf, pos):
    end = buf.index(b"\0", pos)
    return buf[pos:end].decode("utf-8"), end + 1


def parse(path):
    """원본(또는 우리가 만든) UnityFS 번들 -> dict(header, nodes, stream)."""
    raw = open(path, "rb").read()
    sig, p = _cstr(raw, 0)
    if sig != "UnityFS":
        raise ValueError("UnityFS 아님: " + sig)
    version = struct.unpack_from(">I", raw, p)[0]
    p += 4
    player, p = _cstr(raw, p)
    engine, p = _cstr(raw, p)
    size, comp_bi, uncomp_bi, flags = struct.unpack_from(">qIII", raw, p)
    p += 20
    if version >= 7:
        p = (p + 15) & ~15
    if flags & 0x80:  # 블록 정보가 파일 끝
        bi = raw[len(raw) - comp_bi:]
    else:
        bi = raw[p:p + comp_bi]
        p += comp_bi
    if flags & 0x3F:
        bi = lz4.block.decompress(bi, uncompressed_size=uncomp_bi)
    q = 16  # 해시 건너뜀
    n_blocks = struct.unpack_from(">i", bi, q)[0]
    q += 4
    blocks = []
    for _ in range(n_blocks):
        u, c, f = struct.unpack_from(">IIH", bi, q)
        q += 10
        blocks.append((u, c, f))
    n_nodes = struct.unpack_from(">i", bi, q)[0]
    q += 4
    nodes = []
    for _ in range(n_nodes):
        off, sz, nf = struct.unpack_from(">qqI", bi, q)
        q += 20
        name, q = _cstr(bi, q)
        nodes.append((off, sz, nf, name))
    if not (flags & 0x80) and (flags & 0x200):
        p = (p + 15) & ~15
    parts = []
    for u, c, f in blocks:
        chunk = raw[p:p + c]
        p += c
        parts.append(lz4.block.decompress(chunk, uncompressed_size=u) if f & 0x3F else chunk)
    return {
        "version": version, "player": player, "engine": engine,
        "nodes": nodes, "stream": b"".join(parts),
    }


def build(info, stream, out_path):
    """info의 노드 목록(offset/size/flags/name)과 새 스트림으로 번들 파일을 쓴다."""
    blocks = []
    body = bytearray()
    for i in range(0, len(stream), CHUNK):
        chunk = stream[i:i + CHUNK]
        comp = lz4.block.compress(chunk, mode="high_compression", compression=9, store_size=False)
        if len(comp) >= len(chunk):
            comp, f = chunk, 0
        else:
            f = NEW_BLOCK_FLAGS
        blocks.append((len(chunk), len(comp), f))
        body += comp

    bi = bytearray(b"\0" * 16)
    bi += struct.pack(">i", len(blocks))
    for u, c, f in blocks:
        bi += struct.pack(">IIH", u, c, f)
    bi += struct.pack(">i", len(info["nodes"]))
    for off, sz, nf, name in info["nodes"]:
        bi += struct.pack(">qqI", off, sz, nf) + name.encode("utf-8") + b"\0"
    comp_bi = lz4.block.compress(bytes(bi), mode="high_compression", compression=9, store_size=False)

    head = bytearray()
    head += b"UnityFS\0" + struct.pack(">I", info["version"])
    head += info["player"].encode() + b"\0" + info["engine"].encode() + b"\0"
    size_pos = len(head)
    head += struct.pack(">qIII", 0, len(comp_bi), len(bi), NEW_DATA_FLAGS)
    while len(head) % 16:
        head += b"\0"
    total = len(head) + len(body) + len(comp_bi)
    head[size_pos:size_pos + 8] = struct.pack(">q", total)
    with open(out_path, "wb") as f:
        f.write(head)
        f.write(body)
        f.write(comp_bi)
