# Minds Beneath Us 한글패치 설치 스크립트 (v0.4, diff 방식)
#
# 이 패치는 게임 파일(.bundle)을 통째로 배포하지 않고, "원본과 달라진 부분"만 담은 diff(patches\*.xd)를
# 사용자 PC에 이미 설치된 게임의 원본 번들에 적용해서 한글 번들을 만든다.
#   1) 원본 번들의 lz4 압축을 풀어 데이터 스트림을 얻고
#   2) xdelta3(tools\xdelta3.exe)로 diff를 적용해 새 데이터 스트림을 만들고
#   3) 128KB 단위로 lz4 압축해서 번들 파일로 다시 저장한다.
# 결과는 게임 폴더의 StreamingAssets\aa\StandaloneWindows64\ 에 덮어쓴다.
# 덮어쓰기 전에 원본은 _originals_backup\ 폴더에 자동 백업한다(이미 백업이 있으면 그 백업을 원본으로 사용).
#
# 사용법: 이 스크립트를 korean.pat 과 같은 폴더에 두고 실행하면 된다(저장소를 clone 한 경우엔 patches\, tools\).
# 실패하면 install_log.txt 를 개발자에게 보내주세요.

$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    chcp 65001 > $null
} catch {}

$scriptDir = $PSScriptRoot
$logPath = Join-Path $scriptDir "install_log.txt"
$logLines = New-Object System.Collections.Generic.List[string]
function Log([string]$msg, [string]$color = "") {
    $logLines.Add($msg)
    if ($color) { Write-Host $msg -ForegroundColor $color } else { Write-Host $msg }
}
function SaveLog {
    $logLines | Out-File -FilePath $logPath -Encoding UTF8
}
function Pause-Exit([int]$code) {
    SaveLog
    Write-Host ""
    Write-Host "로그: $logPath"
    Read-Host "이 창을 닫으려면 Enter 키를 누르세요"
    exit $code
}

$csharp = @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

public class NodeInfo {
    public long Size;
    public uint Flags;
    public string Name;
}

public static class Lz4 {
    public static void Decompress(byte[] src, int srcOff, int srcLen, byte[] dst, int dstOff, int dstLen) {
        int sp = srcOff, se = srcOff + srcLen, dp = dstOff, de = dstOff + dstLen;
        while (sp < se) {
            int token = src[sp++];
            int lit = token >> 4;
            if (lit == 15) { int b; do { b = src[sp++]; lit += b; } while (b == 255); }
            Buffer.BlockCopy(src, sp, dst, dp, lit);
            sp += lit; dp += lit;
            if (sp >= se) break;
            int off = src[sp] | (src[sp + 1] << 8);
            sp += 2;
            int ml = token & 15;
            if (ml == 15) { int b; do { b = src[sp++]; ml += b; } while (b == 255); }
            ml += 4;
            int mp = dp - off;
            if (off == 0 || mp < dstOff) throw new InvalidDataException("lz4: 잘못된 오프셋");
            for (int i = 0; i < ml; i++) dst[dp++] = dst[mp++];
        }
        if (dp != de) throw new InvalidDataException("lz4: 해제 크기 불일치 (" + dp + " != " + de + ")");
    }

    static void WriteLen(byte[] dst, ref int dp, int v) {
        while (v >= 255) { dst[dp++] = 255; v -= 255; }
        dst[dp++] = (byte)v;
    }

    public static byte[] Compress(byte[] src, int off, int len) {
        byte[] dst = new byte[len + len / 255 + 32];
        int dp = 0;
        int[] table = new int[1 << 16];
        int anchor = off, sp = off, end = off + len;
        int mflimit = end - 12, matchlimit = end - 5;
        if (len >= 13) {
            while (sp <= mflimit) {
                uint seq = BitConverter.ToUInt32(src, sp);
                int h = (int)((seq * 2654435761u) >> 16);
                int rf = table[h] - 1;
                table[h] = sp + 1;
                if (rf >= off && sp - rf < 65536 && BitConverter.ToUInt32(src, rf) == seq) {
                    int mp = sp + 4, rp = rf + 4;
                    while (mp < matchlimit && src[mp] == src[rp]) { mp++; rp++; }
                    int ml = mp - sp - 4;
                    int lit = sp - anchor;
                    dst[dp++] = (byte)(((lit >= 15 ? 15 : lit) << 4) | (ml >= 15 ? 15 : ml));
                    if (lit >= 15) WriteLen(dst, ref dp, lit - 15);
                    Buffer.BlockCopy(src, anchor, dst, dp, lit);
                    dp += lit;
                    int offset = sp - rf;
                    dst[dp++] = (byte)(offset & 255);
                    dst[dp++] = (byte)(offset >> 8);
                    if (ml >= 15) WriteLen(dst, ref dp, ml - 15);
                    sp = mp;
                    anchor = mp;
                    continue;
                }
                sp++;
            }
        }
        int last = end - anchor;
        dst[dp++] = (byte)((last >= 15 ? 15 : last) << 4);
        if (last >= 15) WriteLen(dst, ref dp, last - 15);
        Buffer.BlockCopy(src, anchor, dst, dp, last);
        dp += last;
        byte[] res = new byte[dp];
        Buffer.BlockCopy(dst, 0, res, 0, dp);
        return res;
    }
}

public static class BundleFs {
    const int CHUNK = 0x20000;
    const uint NEW_DATA_FLAGS = 194;
    const ushort NEW_BLOCK_FLAGS = 2;

    static string CStr(byte[] b, ref int p) {
        int s = p;
        while (b[p] != 0) p++;
        string r = Encoding.UTF8.GetString(b, s, p - s);
        p++;
        return r;
    }
    static uint U32(byte[] b, int p) { return ((uint)b[p] << 24) | ((uint)b[p + 1] << 16) | ((uint)b[p + 2] << 8) | b[p + 3]; }
    static int I32(byte[] b, int p) { return (int)U32(b, p); }
    static ushort U16(byte[] b, int p) { return (ushort)((b[p] << 8) | b[p + 1]); }
    static void PutU32(Stream s, uint v) { s.WriteByte((byte)(v >> 24)); s.WriteByte((byte)(v >> 16)); s.WriteByte((byte)(v >> 8)); s.WriteByte((byte)v); }
    static void PutU16(Stream s, ushort v) { s.WriteByte((byte)(v >> 8)); s.WriteByte((byte)v); }

    // 원본 번들을 읽어 압축 푼 데이터 스트림을 돌려준다.
    public static byte[] ReadStream(string path) {
        byte[] raw = File.ReadAllBytes(path);
        int p = 0;
        string sig = CStr(raw, ref p);
        if (sig != "UnityFS") throw new InvalidDataException("UnityFS 번들이 아님: " + sig);
        uint version = U32(raw, p); p += 4;
        CStr(raw, ref p);
        CStr(raw, ref p);
        p += 8; // 파일 크기
        int compBi = I32(raw, p); p += 4;
        int uncompBi = I32(raw, p); p += 4;
        uint flags = U32(raw, p); p += 4;
        if (version >= 7) p = (p + 15) & ~15;
        byte[] bi = new byte[uncompBi];
        int biStart;
        if ((flags & 0x80) != 0) biStart = raw.Length - compBi;
        else { biStart = p; p += compBi; }
        if ((flags & 0x3F) != 0) Lz4.Decompress(raw, biStart, compBi, bi, 0, uncompBi);
        else Buffer.BlockCopy(raw, biStart, bi, 0, uncompBi);
        int q = 16;
        int nBlocks = I32(bi, q); q += 4;
        uint[] us = new uint[nBlocks]; uint[] cs = new uint[nBlocks]; ushort[] fl = new ushort[nBlocks];
        long total = 0;
        for (int i = 0; i < nBlocks; i++) {
            us[i] = U32(bi, q); cs[i] = U32(bi, q + 4); fl[i] = U16(bi, q + 8); q += 10;
            total += us[i];
        }
        if ((flags & 0x80) == 0 && (flags & 0x200) != 0) p = (p + 15) & ~15;
        byte[] stream = new byte[total];
        long dp = 0;
        for (int i = 0; i < nBlocks; i++) {
            if ((fl[i] & 0x3F) != 0) Lz4.Decompress(raw, p, (int)cs[i], stream, (int)dp, (int)us[i]);
            else Buffer.BlockCopy(raw, p, stream, (int)dp, (int)us[i]);
            p += (int)cs[i];
            dp += us[i];
        }
        return stream;
    }

    public static void Write(string outPath, byte[] stream, uint version, string player, string engine, List<NodeInfo> nodes) {
        List<byte[]> blocks = new List<byte[]>();
        List<uint> usz = new List<uint>();
        List<ushort> bfl = new List<ushort>();
        long bodyLen = 0;
        for (int i = 0; i < stream.Length; i += CHUNK) {
            int n = Math.Min(CHUNK, stream.Length - i);
            byte[] comp = Lz4.Compress(stream, i, n);
            ushort f = NEW_BLOCK_FLAGS;
            if (comp.Length >= n) {
                comp = new byte[n];
                Buffer.BlockCopy(stream, i, comp, 0, n);
                f = 0;
            }
            blocks.Add(comp); usz.Add((uint)n); bfl.Add(f);
            bodyLen += comp.Length;
        }
        MemoryStream bi = new MemoryStream();
        for (int i = 0; i < 16; i++) bi.WriteByte(0);
        PutU32(bi, (uint)blocks.Count);
        for (int i = 0; i < blocks.Count; i++) { PutU32(bi, usz[i]); PutU32(bi, (uint)blocks[i].Length); PutU16(bi, bfl[i]); }
        PutU32(bi, (uint)nodes.Count);
        long off = 0;
        foreach (NodeInfo nd in nodes) {
            PutU32(bi, (uint)(off >> 32)); PutU32(bi, (uint)off);
            PutU32(bi, (uint)(nd.Size >> 32)); PutU32(bi, (uint)nd.Size);
            PutU32(bi, nd.Flags);
            byte[] nb = Encoding.UTF8.GetBytes(nd.Name);
            bi.Write(nb, 0, nb.Length); bi.WriteByte(0);
            off += nd.Size;
        }
        if (off != stream.Length) throw new InvalidDataException("노드 크기 합이 스트림 크기와 다름");
        byte[] biRaw = bi.ToArray();
        byte[] biComp = Lz4.Compress(biRaw, 0, biRaw.Length);

        MemoryStream head = new MemoryStream();
        byte[] sg = Encoding.UTF8.GetBytes("UnityFS"); head.Write(sg, 0, sg.Length); head.WriteByte(0);
        PutU32(head, version);
        byte[] pb = Encoding.UTF8.GetBytes(player); head.Write(pb, 0, pb.Length); head.WriteByte(0);
        byte[] eb = Encoding.UTF8.GetBytes(engine); head.Write(eb, 0, eb.Length); head.WriteByte(0);
        long sizePos = head.Position;
        for (int i = 0; i < 8; i++) head.WriteByte(0);
        PutU32(head, (uint)biComp.Length);
        PutU32(head, (uint)biRaw.Length);
        PutU32(head, NEW_DATA_FLAGS);
        while (head.Position % 16 != 0) head.WriteByte(0);
        long total = head.Position + bodyLen + biComp.Length;
        byte[] hb = head.ToArray();
        for (int i = 0; i < 8; i++) hb[sizePos + i] = (byte)(total >> (56 - 8 * i));

        using (FileStream fs = new FileStream(outPath, FileMode.Create, FileAccess.Write)) {
            fs.Write(hb, 0, hb.Length);
            for (int i = 0; i < blocks.Count; i++) fs.Write(blocks[i], 0, blocks[i].Length);
            fs.Write(biComp, 0, biComp.Length);
        }
    }
}
'@

function Get-Sha256([string]$path) {
    (Get-FileHash -Path $path -Algorithm SHA256).Hash.ToLower()
}

function Find-GameRoot {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Steam\steamapps\common\MindsBeneathUs",
        "${env:ProgramFiles}\Steam\steamapps\common\MindsBeneathUs",
        "C:\Steam\steamapps\common\MindsBeneathUs",
        "D:\Steam\steamapps\common\MindsBeneathUs",
        "E:\Steam\steamapps\common\MindsBeneathUs"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "MindsBeneathUs_Data")) { return $c }
    }
    return $null
}

Log "=== Minds Beneath Us 한글패치 설치 (v0.4) ===" "Cyan"
Log ""
Log "시작: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  PowerShell $($PSVersionTable.PSVersion)  64bit=$([Environment]::Is64BitProcess)"

if (-not [Environment]::Is64BitProcess) {
    Log "오류: 64비트 PowerShell 에서 실행해야 합니다 (큰 번들을 메모리에 올리기 때문)." "Red"
    Pause-Exit 1
}

$gameRoot = Find-GameRoot
if (-not $gameRoot) {
    Write-Host "게임 설치 폴더를 자동으로 못 찾았어요."
    $gameRoot = Read-Host "MindsBeneathUs.exe가 있는 폴더 경로를 직접 입력해주세요 (예: D:\Steam\steamapps\common\MindsBeneathUs)"
}
$targetDir = Join-Path $gameRoot "MindsBeneathUs_Data\StreamingAssets\aa\StandaloneWindows64"
if (-not (Test-Path $targetDir)) {
    Log "오류: 대상 폴더를 찾을 수 없습니다: $targetDir" "Red"
    Pause-Exit 1
}
Log "게임 폴더: $gameRoot"
Log "대상 위치: $targetDir"

# korean.pat(내용은 zip: patches\ + tools\xdelta3.exe)이 있으면 임시 폴더에 풀어서 쓰고,
# 없으면(저장소를 그대로 clone 한 경우) 스크립트 옆의 patches\ , tools\ 를 그대로 쓴다.
$tmpDir = Join-Path $env:TEMP ("mbu_kr_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpDir | Out-Null
$patFile = Join-Path $scriptDir "korean.pat"
if (Test-Path $patFile) {
    Log "패치 데이터(korean.pat) 준비 중..."
    $tmpZip = Join-Path $tmpDir "korean.zip"
    Copy-Item -Path $patFile -Destination $tmpZip
    Expand-Archive -Path $tmpZip -DestinationPath (Join-Path $tmpDir "pat") -Force
    Remove-Item $tmpZip -Force
    $patchDir = Join-Path $tmpDir "pat\patches"
    $xdelta = Join-Path $tmpDir "pat\tools\xdelta3.exe"
} else {
    $patchDir = Join-Path $scriptDir "patches"
    $xdelta = Join-Path $scriptDir "tools\xdelta3.exe"
}
if (-not (Test-Path $patchDir) -or -not (Test-Path $xdelta)) {
    Log "오류: 패치 데이터(korean.pat 또는 patches\, tools\xdelta3.exe)를 찾을 수 없습니다. 압축을 다 풀고 실행했는지 확인해주세요." "Red"
    Pause-Exit 1
}
$metas = Get-ChildItem -Path $patchDir -Filter "*.meta"
if ($metas.Count -eq 0) {
    Log "오류: patches 폴더에 .meta 파일이 없습니다." "Red"
    Pause-Exit 1
}

try {
    if (-not ("BundleFs" -as [type])) { Add-Type -TypeDefinition $csharp -Language CSharp }
} catch {
    Log "오류: 내장 C# 코드를 컴파일하지 못했습니다: $($_.Exception.Message)" "Red"
    Pause-Exit 1
}

$backupDir = Join-Path $targetDir "_originals_backup"
$hadExistingInstall = Test-Path $backupDir
if ($hadExistingInstall) {
    Log "기존 설치가 감지되었습니다 — 백업된 원본을 기준으로 업데이트합니다." "Yellow"
} else {
    Log "처음 설치합니다."
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}
Log ""

$installed = 0
$failed = @()
$skipped = @()
$idx = 0

foreach ($metaFile in $metas) {
    $idx++
    $bundleName = $metaFile.Name -replace '\.meta$', ''
    $xdPath = Join-Path $patchDir ($bundleName + ".xd")
    $targetPath = Join-Path $targetDir $bundleName
    $backupPath = Join-Path $backupDir $bundleName
    Log "[$idx/$($metas.Count)] $bundleName"

    try {
        if (-not (Test-Path $targetPath)) {
            Log "  [건너뜀] 게임 폴더에 없는 파일 (게임 버전이 다를 수 있음)" "Yellow"
            $skipped += $bundleName
            continue
        }

        $meta = @{}
        $nodes = New-Object 'System.Collections.Generic.List[NodeInfo]'
        foreach ($line in (Get-Content -Path $metaFile.FullName -Encoding UTF8)) {
            if ($line.StartsWith("node`t")) {
                $p = $line.Split("`t")
                $n = New-Object NodeInfo
                $n.Flags = [uint32]$p[1]; $n.Size = [int64]$p[2]; $n.Name = $p[3]
                $nodes.Add($n)
            } elseif ($line.Contains("=")) {
                $k, $v = $line.Split("=", 2)
                $meta[$k] = $v
            }
        }

        # 원본 파일 결정: 백업이 있으면 백업(원본), 없으면 게임 폴더의 현재 파일.
        if (Test-Path $backupPath) { $srcPath = $backupPath } else { $srcPath = $targetPath }
        $srcHash = Get-Sha256 $srcPath
        if ($srcHash -ne $meta["orig_sha256"]) {
            if ($srcPath -eq $targetPath) {
                Log "  [건너뜀] 원본 파일이 아닙니다 (이미 다른 패치가 적용됐거나 게임 버전이 다름). uninstall.ps1 로 원본 복원 후 다시 시도하세요." "Yellow"
            } else {
                Log "  [건너뜀] 백업 파일이 원본과 다릅니다. 게임 무결성 검사(Steam)로 원본 복구 후 _originals_backup 폴더를 지우고 다시 시도하세요." "Yellow"
            }
            $skipped += $bundleName
            continue
        }

        Log "  원본 압축 해제 중..."
        $stream = [BundleFs]::ReadStream($srcPath)
        $streamFile = Join-Path $tmpDir "stream.bin"
        $newFile = Join-Path $tmpDir "new.bin"
        [System.IO.File]::WriteAllBytes($streamFile, $stream)
        $stream = $null

        Log "  diff 적용 중..."
        & $xdelta -d -f -s $streamFile $xdPath $newFile
        if ($LASTEXITCODE -ne 0) { throw "xdelta3 실패 (exit $LASTEXITCODE)" }
        Remove-Item $streamFile -Force

        $newStream = [System.IO.File]::ReadAllBytes($newFile)
        Remove-Item $newFile -Force
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $h = ([BitConverter]::ToString($sha.ComputeHash($newStream)) -replace '-', '').ToLower()
        if ($h -ne $meta["stream_sha256"]) { throw "diff 적용 결과 검증 실패 (해시 불일치)" }

        Log "  번들 저장 중 (lz4 압축)..."
        $outTmp = Join-Path $tmpDir "out.bundle"
        [BundleFs]::Write($outTmp, $newStream, [uint32]$meta["version"], $meta["player"], $meta["engine"], $nodes)
        $newStream = $null

        if (-not (Test-Path $backupPath)) {
            Copy-Item -Path $targetPath -Destination $backupPath
        }
        Copy-Item -Path $outTmp -Destination $targetPath -Force
        Remove-Item $outTmp -Force
        $installed++
        Log "  [설치됨]" "Green"
    } catch {
        Log "  [실패] $($_.Exception.Message)" "Red"
        $failed += $bundleName
    }
    [GC]::Collect()
}

Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue

Log ""
if ($failed.Count -eq 0 -and $skipped.Count -eq 0) {
    Log "완료: 모두 설치되었습니다. ($installed 개 파일)" "Green"
} else {
    Log "결과: 설치 $installed 개 / 건너뜀 $($skipped.Count) 개 / 실패 $($failed.Count) 개" "Red"
    foreach ($f in $skipped) { Log "  건너뜀: $f" }
    foreach ($f in $failed) { Log "  실패: $f" }
    Log "일부 파일에 패치가 적용되지 않아 해당 부분은 원문이 나올 수 있습니다. install_log.txt 를 개발자에게 보내주세요." "Red"
}
Log "백업 위치: $backupDir"
Log ""
Log "게임 실행 후 설정 > 언어 > English 로 변경하면 한글이 나옵니다."
Log "제거하려면 uninstall.ps1 을 실행하세요."
Pause-Exit 0
