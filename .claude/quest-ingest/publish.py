import re, subprocess, sys
from pathlib import Path
import pypdfium2 as pdfium
STAGE = Path("/tmp/quest-scans/quest")
WORKS = Path("/Users/siraj/Indian Liberals Website/apps/site/src/content/primary-works")
WR = "/Users/siraj/Indian Liberals Website/apps/site/node_modules/.bin/wrangler"
CWD = "/Users/siraj/Indian Liberals Website/apps/site"
HOST = "https://archive.indianliberals.in"
cov = Path("/tmp/quest-covers"); cov.mkdir(exist_ok=True)
def put(key, path, ct):
    for a in range(1, 6):
        r = subprocess.run([WR,"r2","object","put",f"indianliberals-archive/{key}",
                            "--file",str(path),"--content-type",ct,"--remote"],
                           cwd=CWD, capture_output=True, text=True)
        if r.returncode == 0 and "ERROR" not in (r.stderr or ""): return True
        import time; time.sleep(a*a*2)
    return False
for num in sys.argv[1:]:
    slug=f"qt{num}"; md=WORKS/f"{slug}.md"; pdf=STAGE/f"QT{num}.pdf"
    if not md.exists(): print(f"SKIP {slug}"); continue
    t=md.read_text(encoding="utf-8")
    if not put(f"quest/{slug}.pdf", pdf, "application/pdf"): print(f"FAIL {slug} pdf"); continue
    doc=pdfium.PdfDocument(str(pdf)); pg=doc[0]
    out=cov/f"{slug}.webp"
    pg.render(scale=480/pg.get_size()[0]).to_pil().convert("RGB").save(out,"WEBP",quality=80)
    doc.close()
    if not put(f"covers/{slug}.webp", out, "image/webp"): print(f"FAIL {slug} cover"); continue
    pu, cu = f"{HOST}/quest/{slug}.pdf", f"{HOST}/covers/{slug}.webp"
    if re.search(r"^pdf_url:", t, re.M): t=re.sub(r'^pdf_url: .*$', f'pdf_url: {pu}', t, count=1, flags=re.M)
    else:
        L=t.split("\n"); s=next(i for i,l in enumerate(L) if l=="publication:"); e=s+1
        while e<len(L) and (L[e].startswith(" ") or L[e]==""): e+=1
        L.insert(e, f"pdf_url: {pu}"); t="\n".join(L)
    if re.search(r"^cover_image:", t, re.M): t=re.sub(r'^cover_image: .*$', f'cover_image: "{cu}"', t, count=1, flags=re.M)
    else: t=re.sub(r'^(pdf_url: .*)$', rf'\1\ncover_image: "{cu}"', t, count=1, flags=re.M)
    md.write_text(t, encoding="utf-8"); print(f"OK   {slug} -> {pu}")
