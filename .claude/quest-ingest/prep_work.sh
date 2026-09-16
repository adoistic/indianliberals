#!/bin/zsh
# Build a self-contained working directory for ONE Quest issue, for ONE subagent.
#
# Quest issues run 70-130 pages, far past the extractor's 20-page default, so
# each agent gets the WHOLE issue: the metadata + summary schemas, rasterised
# front matter (cover/masthead/contents, where display type OCRs badly), the
# complete page-delimited text layer, and a renderer for any page it wants to
# see. Scans are staged just-in-time and reaped after publish — this machine's
# Data volume runs chronically full.
set -e
REPO="/Users/siraj/Indian Liberals Website"
STAGE="/tmp/quest-scans"
SRC="/Users/siraj/Downloads/drive-download-20260915T160627Z-1-001"
export LLM_EXTRACT_PDF_ROOT="$STAGE"
cd "$REPO"
QT="$1"; FRONT=${2:-14}
mkdir -p "$STAGE/quest"
PDF="$STAGE/quest/${QT}.pdf"
if [ ! -f "$PDF" ]; then
  if [ -f "$SRC/${QT}.pdf" ]; then cp "$SRC/${QT}.pdf" "$PDF"
  else curl -sS -o "$PDF" "https://archive.indianliberals.in/quest/$(echo $QT | tr 'A-Z' 'a-z').pdf"; fi
fi
PP=$(pdfinfo "$PDF" | awk '/^Pages/{print $2}')

MD=$(.venv-extract/bin/python scripts/llm-extract/driver.py prep "quest/${QT}.pdf" \
       --job metadata.a --pages-wanted "$FRONT" 2>/dev/null | grep "Request dir:" | awk '{print $3}')
SD=$(.venv-extract/bin/python scripts/llm-extract/driver.py prep "quest/${QT}.pdf" \
       --job summary --pages-wanted 1 2>/dev/null | grep "Request dir:" | awk '{print $3}')
cp "$SD/system.txt" "$MD/summary_system.txt"; cp "$SD/user.txt" "$MD/summary_user.txt"; rm -rf "$SD"

.venv-extract/bin/python - "$PDF" "$MD/fulltext.txt" "$PP" <<'PY'
import sys, subprocess
pdf, out, pp = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(out, "w", encoding="utf-8") as f:
    for p in range(1, pp + 1):
        t = subprocess.run(["pdftotext","-f",str(p),"-l",str(p),pdf,"-"],
                           capture_output=True, text=True).stdout
        f.write(f"\n===== PDF PAGE {p} of {pp} =====\n{t.rstrip()}\n")
PY

cat > "$MD/render_page.sh" <<RP
#!/bin/zsh
# Render one page of this issue to a JPEG and print its path. Usage: ./render_page.sh 57
"$REPO/.venv-extract/bin/python" - "\$1" <<'PY'
import sys, pypdfium2 as pdfium
p = int(sys.argv[1]); doc = pdfium.PdfDocument("$PDF")
dest = "$MD/ondemand-page-%03d.jpg" % p
doc[p-1].render(scale=2.0).to_pil().convert("RGB").save(dest, "JPEG", quality=85)
doc.close(); print(dest)
PY
RP
chmod +x "$MD/render_page.sh"

# printed-folio offset hint. It has been WRONG (OCR noise); agents must verify.
.venv-extract/bin/python - "$MD/fulltext.txt" > "$MD/offset_hint.txt" <<'PY'
import re, sys
txt = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
b = re.split(r"===== PDF PAGE (\d+) of \d+ =====", txt)
votes = {}
for i in range(1, len(b) - 1, 2):
    pg = int(b[i])
    for m in re.finditer(r"(?m)^\s*(\d{1,3})\s*$", b[i+1]):
        f = int(m.group(1))
        if 1 <= f <= 400: votes[f - pg] = votes.get(f - pg, 0) + 1
print("Candidate offsets (printed_folio - pdf_page), most frequent first:")
for off, n in sorted(votes.items(), key=lambda kv: -kv[1])[:4]:
    print(f"  offset {off:+d}  seen {n} times")
print("\nVERIFY against rendered pages. The offset is often NOT constant.")
PY
echo "$QT ready: $PP pages | $(ls "$MD"/page-*.jpg | wc -l | tr -d ' ') front images | fulltext $(wc -c < "$MD/fulltext.txt" | tr -d ' ') chars"
echo "$(sed -n 2p "$MD/offset_hint.txt")"
echo "DIR=$MD"
