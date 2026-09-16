#!/usr/bin/env python3
"""Delete a Quest issue's local scans once the archive copy is proven good.

This machine's Data volume runs chronically full. Nothing is deleted on trust:
for each issue this re-checks that the work's markdown carries a pdf_url, the R2
object answers 200, its Content-Length equals the local byte size, and the cover
object answers 200. Only then are the staged copy and the original download
removed. A mismatch leaves both alone and says so. The scan stays recoverable
from R2 and from CCS's Drive.

Usage: reap.py 025 026 ...
"""
import re, subprocess, sys
from pathlib import Path
STAGE = Path("/tmp/quest-scans/quest")
DL = Path("/Users/siraj/Downloads/drive-download-20260915T160627Z-1-001")
WORKS = Path("/Users/siraj/Indian Liberals Website/apps/site/src/content/primary-works")
HOST = "https://archive.indianliberals.in"

def head(url):
    r = subprocess.run(["curl", "-sI", url], capture_output=True, text=True).stdout
    c = re.search(r"HTTP/[\d.]+ (\d+)", r); l = re.search(r"(?im)^content-length:\s*(\d+)", r)
    return (int(c.group(1)) if c else 0), (int(l.group(1)) if l else -1)

freed = 0
for a in sys.argv[1:]:
    num = a.lower().replace("qt", "").zfill(3); slug = f"qt{num}"
    md = WORKS / f"{slug}.md"
    if not md.exists() or not re.search(r"^pdf_url:", md.read_text(encoding="utf-8"), re.M):
        print(f"KEEP {slug}: not ingested"); continue
    code, remote = head(f"{HOST}/quest/{slug}.pdf")
    ccode, _ = head(f"{HOST}/covers/{slug}.webp")
    if code != 200 or ccode != 200:
        print(f"KEEP {slug}: R2 pdf={code} cover={ccode}"); continue
    targets = [STAGE / f"QT{num}.pdf", DL / f"QT{num}.pdf"]
    sizes = {p: p.stat().st_size for p in targets if p.exists()}
    if not sizes: print(f"OK   {slug}: already reaped"); continue
    bad = [str(p) for p, s in sizes.items() if s != remote]
    if bad: print(f"KEEP {slug}: local bytes != R2 ({remote}) {bad}"); continue
    for p in sizes: freed += sizes[p]; p.unlink()
    print(f"REAP {slug}: verified on R2 ({remote} bytes), removed {len(sizes)} copy/copies")
print(f"\nfreed {freed/1e6:.0f} MB")
