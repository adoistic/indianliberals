#!/usr/bin/env python3
"""Branded Open Graph cards for every page with a picture.

Every detail page on indianliberals.in advertises itself to social networks
with a 1200x630 card hosted on R2 under the og/ prefix, addressed by
convention (og/w/<work>.jpg, og/t/<thinker>.jpg, og/m/<musing>.jpg,
og/o/<opinion>.jpg — see apps/site/src/lib/og.ts). This script is the whole
pipeline: it reads the content collections, works out what every card should
say and show, renders the ones whose inputs changed, and uploads them.

It keeps a manifest (og/manifest.json) mapping card key -> a hash of the
card's inputs (title, eyebrow, byline, source image). A run therefore only
re-renders what actually changed: a new work, a corrected title, a replaced
cover. The GitHub workflow og-cards.yml runs it on every content push, which
is what makes cards appear for new works with nobody asked.

Modes:
  # render whatever changed into --out, upload through the CMS worker
  python3 scripts/og/og_cards.py sync --out /tmp/og_out \
      --endpoint https://cms.indianliberals.in/api/og-put --token $OG_PUSH_TOKEN

  # same, uploading with wrangler instead (local use, OAuth)
  python3 scripts/og/og_cards.py sync --out /tmp/og_out --wrangler

  # force everything, or preview without uploading
  ... sync --all --out /tmp/og_out --no-upload

Needs: pillow (with raqm for Indic shaping — the wheels have it), pyyaml.
Fonts live in scripts/og/fonts/ (converted from the site's own fontsource
packages); the crane comes from the site's brand assets.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONTENT = os.path.join(ROOT, "apps", "site", "src", "content")
PUBLIC = os.path.join(ROOT, "apps", "site", "public")
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
ARCHIVE = "https://archive.indianliberals.in"
BUCKET = "indianliberals-archive"
UA = {"User-Agent": "Mozilla/5.0 (og-cards)"}

# ── The palette, sampled from the shipped cards ────────────────────────

SAFFRON = (231, 104, 9)
FOREST_LIGHT = (40, 66, 42)
FOREST_DARK = (12, 46, 14)
GOLD = (226, 200, 118)
CREAM = (247, 250, 246)

W, H = 1200, 630
BAR = 12                 # saffron top bar
IMG_BOX = (430, 456)     # the picture never grows past this
IMG_X, IMG_TOP, IMG_BOT = 96, 87, 543
TEXT_GAP = 72            # picture -> text column
RIGHT_MARGIN = 96

# ── Fonts ──────────────────────────────────────────────────────────────

_fonts: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(os.path.join(FONTS, name), size)
    return _fonts[key]


def title_font_name(text: str) -> str:
    """Serif for the script the title is written in."""
    for ch in text:
        code = ord(ch)
        if 0x0900 <= code <= 0x097F:
            return "NotoSerifDevanagari-Bold.ttf"
        if 0x0980 <= code <= 0x09FF:
            return "NotoSerifBengali-Bold.ttf"
        if 0x0A80 <= code <= 0x0AFF:
            return "NotoSerifGujarati-Bold.ttf"
    return "SourceSerif4-Bold.ttf"


# ── Text layout ────────────────────────────────────────────────────────


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, width: int,
         max_lines: int) -> list[str]:
    """Greedy wrap; the last permitted line is cut with a three-dot tail."""
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width or not line:
            line = trial
            continue
        lines.append(line)
        line = word
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and line:
        lines.append(line)
        line = ""
    if line or len(lines) > max_lines:
        # Something did not fit: shorten the last line until the dots do.
        last = lines[-1]
        while last and draw.textlength(last + "...", font=fnt) > width:
            last = last[:-1].rstrip()
        lines[-1] = last + "..."
    return lines


def tracked(draw: ImageDraw.ImageDraw, pos: tuple[int, int], text: str,
            fnt: ImageFont.FreeTypeFont, fill: tuple, tracking: int) -> int:
    """Draw with letter-spacing; returns the x it finished at."""
    x, y = pos
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return int(x)


# ── The card itself ────────────────────────────────────────────────────

_crane: Image.Image | None = None


def crane_mark(height: int) -> Image.Image:
    """The brand crane as a white silhouette."""
    global _crane
    if _crane is None:
        raw = Image.open(os.path.join(PUBLIC, "brand", "brand-mark-crane.png")).convert("RGBA")
        white = Image.new("RGBA", raw.size, (255, 255, 255, 255))
        white.putalpha(raw.getchannel("A"))
        _crane = white.crop(white.getbbox())
    scale = height / _crane.height
    return _crane.resize((max(1, round(_crane.width * scale)), height), Image.LANCZOS)


def backdrop(source: Image.Image | None) -> Image.Image:
    """Forest gradient, with the card's own picture blurred into it."""
    base = Image.new("RGB", (W, H))
    px = base.load()
    for y in range(H):
        for x in range(0, W, 4):
            t = (x / W + y / H) / 2
            c = tuple(round(a + (b - a) * t) for a, b in zip(FOREST_LIGHT, FOREST_DARK))
            for dx in range(4):
                if x + dx < W:
                    px[x + dx, y] = c
    if source is not None:
        big = source.convert("RGB").resize((W, H))
        big = big.filter(ImageFilter.GaussianBlur(radius=48))
        base = Image.blend(base, Image.blend(base, big, 0.55), 0.62)
    # A vignette keeps the corners quiet whatever the picture held.
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((-W * 0.35, -H * 0.55, W * 1.35, H * 1.55), fill=90)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=120))
    dark = Image.new("RGB", (W, H), FOREST_DARK)
    return Image.composite(base, dark, mask.point(lambda v: 255 - v))


def render_card(record: dict, image: Image.Image | None) -> Image.Image:
    card = backdrop(image)
    draw = ImageDraw.Draw(card)
    draw.rectangle((0, 0, W, BAR), fill=SAFFRON)

    # The picture, framed in white, on the left.
    text_x = IMG_X  # if there is no picture the text simply starts at the margin
    if image is not None:
        img = image.convert("RGB")
        scale = min(IMG_BOX[0] / img.width, IMG_BOX[1] / img.height)
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.LANCZOS)
        border = 8
        framed = Image.new("RGB", (img.width + border * 2, img.height + border * 2),
                           (255, 255, 255))
        framed.paste(img, (border, border))
        fy = IMG_TOP + (IMG_BOT - IMG_TOP - framed.height) // 2
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rectangle((IMG_X + 6, fy + 10, IMG_X + framed.width + 6, fy + framed.height + 10),
                     fill=(0, 0, 0, 110))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=14))
        card = Image.alpha_composite(card.convert("RGBA"), shadow).convert("RGB")
        card.paste(framed, (IMG_X, fy))
        draw = ImageDraw.Draw(card)
        text_x = IMG_X + framed.width + TEXT_GAP

    col_width = W - RIGHT_MARGIN - text_x

    # Title first, since its size decides the block's height.
    title = record["title"]
    tf_name = title_font_name(title)
    lines: list[str] = []
    size = 64
    for size in (64, 56, 50):
        lines = wrap(draw, title, font(tf_name, size), col_width, 4)
        if len(lines) <= (2 if size == 64 else 3 if size == 56 else 4):
            break
    line_h = round(size * 1.18)

    eyebrow_f = font("SourceSans3-Bold.ttf", 26)
    sub_f = font("SourceSerif4-Regular.ttf", 34)
    sub_lines = wrap(draw, record["sub"], sub_f, col_width, 2) if record.get("sub") else []

    block = 26 + 26 + len(lines) * line_h + (14 + len(sub_lines) * 44 if sub_lines else 0)
    y = max(BAR + 60, 285 - block // 2)

    tracked(draw, (text_x, y), record["eyebrow"].upper(), eyebrow_f, GOLD, 2)
    y += 26 + 26
    for line in lines:
        draw.text((text_x, y), line, font=font(tf_name, size), fill=CREAM)
        y += line_h
    if sub_lines:
        y += 14
        for line in sub_lines:
            draw.text((text_x, y), line, font=sub_f, fill=GOLD)
            y += 44

    # The wordmark, aligned with the text column, near the foot.
    mark = crane_mark(44)
    my = 536
    card.paste(mark, (text_x, my + 2), mark)
    wx = text_x + mark.width + 16
    name_f = font("SourceSans3-Bold.ttf", 30)
    tracked(draw, (wx, my), "INDIAN LIBERALS", name_f, CREAM, 1)
    tracked(draw, (wx, my + 40), "AN ONLINE ARCHIVE", font("SourceSans3-SemiBold.ttf", 21),
            GOLD, 2)

    return card


# ── What every card should hold ────────────────────────────────────────


def load_front(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None
    match = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None


def pretty(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


def year_of(value) -> str:
    text = str(value or "")
    match = re.search(r"\d{4}", text)
    return match.group(0) if match else ""


def thinker_names(root: str) -> dict[str, str]:
    names = {}
    directory = os.path.join(root, "thinkers")
    for name in os.listdir(directory):
        if not name.endswith(".md"):
            continue
        data = load_front(os.path.join(directory, name))
        if data:
            canonical = (data.get("name") or {}).get("canonical")
            if canonical:
                names[name[:-3]] = str(canonical)
    return names


def author_id(ref) -> str:
    """The slug out of an authors[] entry, in either shape it comes in.

    A thinker is a bare string. An organisation has to be written as
    ``{collection: organisations, id: forum-of-free-enterprise}``, because a
    bare string always resolves through the thinkers arm of the schema's union
    and the byline silently disappears. Both forms are in the corpus.
    """
    if isinstance(ref, dict):
        return str(ref.get("id") or "")
    return str(ref or "")


def listed(data: dict) -> bool:
    return not data.get("draft") and not data.get("hide_from_index")


def collect() -> list[dict]:
    """One record per card the archive should have."""
    names = thinker_names(CONTENT)
    records: list[dict] = []

    def add(key: str, title, eyebrow: str, sub: str, image: str | None):
        if not title or not image:
            return
        records.append({
            "key": key,
            "title": str(title),
            "eyebrow": eyebrow,
            "sub": sub,
            "image": image,
        })

    for name in os.listdir(os.path.join(CONTENT, "primary-works")):
        if not name.endswith(".md"):
            continue
        data = load_front(os.path.join(CONTENT, "primary-works", name))
        if not data or not listed(data):
            continue
        title = (data.get("title") or {}).get("main")
        year = year_of((data.get("publication") or {}).get("year"))
        kind = pretty(str(data.get("work_type") or "work"))
        eyebrow = f"{kind} · {year}" if year else kind
        authors = [names.get(author_id(a), "") for a in (data.get("authors") or [])[:3]]
        authors = [a for a in authors if a]
        sub = "by " + ", ".join(authors) if authors else ""
        add(f"og/w/{name[:-3]}.jpg", title, eyebrow, sub, data.get("cover_image"))

    for name in os.listdir(os.path.join(CONTENT, "thinkers")):
        if not name.endswith(".md"):
            continue
        data = load_front(os.path.join(CONTENT, "thinkers", name))
        if not data or not listed(data):
            continue
        portrait = data.get("portrait") or {}
        image = portrait.get("photo") or portrait.get("caricature")
        title = (data.get("name") or {}).get("canonical")
        eyebrow = pretty(str(data.get("tradition") or "thinker"))
        birth, death = data.get("birth_year"), data.get("death_year")
        years = f"{birth}–{death}" if birth and death else (str(birth) if birth else "")
        jobs = ", ".join(pretty(str(v)) for v in (data.get("vocations") or [])[:3])
        sub = " · ".join(part for part in (years, jobs) if part)
        add(f"og/t/{name[:-3]}.jpg", title, eyebrow, sub, image)

    for collection, prefix, label in (("musings", "m", "Musing"), ("opinions", "o", "Opinion")):
        for name in os.listdir(os.path.join(CONTENT, collection)):
            if not name.endswith(".md"):
                continue
            data = load_front(os.path.join(CONTENT, collection, name))
            if not data or not listed(data):
                continue
            year = year_of(data.get("pubDate"))
            eyebrow = f"{label} · {year}" if year else label
            if collection == "musings":
                author = names.get(str(data.get("author") or ""), "")
                sub = f"by {author}" if author else ""
            else:
                sub = str(data.get("author_name") or "")
            add(f"og/{prefix}/{name[:-3]}.jpg", data.get("title"), eyebrow, sub,
                data.get("hero_image"))

    return records


# ── Sources, hashes, manifest ──────────────────────────────────────────


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def image_stamp(ref: str) -> str:
    """Something that changes when the picture changes."""
    if ref.startswith("http"):
        request = urllib.request.Request(ref, method="HEAD", headers=UA)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.headers.get("etag") or response.headers.get("content-length") or "?"
        except Exception:
            return "missing"
    local = os.path.join(PUBLIC, ref.lstrip("/"))
    try:
        with open(local, "rb") as handle:
            return hashlib.sha1(handle.read()).hexdigest()[:16]
    except OSError:
        return "missing"


def input_hash(record: dict, stamp: str) -> str:
    payload = json.dumps(
        [record["title"], record["eyebrow"], record["sub"], record["image"], stamp, "v1"],
        ensure_ascii=False,
    )
    return hashlib.sha1(payload.encode()).hexdigest()


def load_image(ref: str) -> Image.Image | None:
    try:
        if ref.startswith("http"):
            return Image.open(io.BytesIO(fetch(ref)))
        return Image.open(os.path.join(PUBLIC, ref.lstrip("/")))
    except Exception:
        return None


def remote_manifest() -> dict:
    try:
        return json.loads(fetch(f"{ARCHIVE}/og/manifest.json"))
    except Exception:
        return {}


# ── Upload ─────────────────────────────────────────────────────────────


def put_wrangler(key: str, path: str) -> bool:
    result = subprocess.run(
        ["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{key}", "--file", path,
         "--content-type", "application/json" if key.endswith(".json") else "image/jpeg",
         "--cache-control", "public, max-age=86400", "--remote"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return result.returncode == 0


def put_endpoint(endpoint: str, token: str, key: str, path: str) -> bool:
    with open(path, "rb") as handle:
        body = handle.read()
    request = urllib.request.Request(
        f"{endpoint}?key={urllib.parse.quote(key)}",
        data=body,
        method="PUT",
        headers={
            "X-Og-Token": token,
            "Content-Type": "application/json" if key.endswith(".json") else "image/jpeg",
            # Cloudflare's browser integrity check 403s urllib's default
            # agent (error 1010) before the Worker ever sees the request.
            **UA,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status < 300
    except Exception as error:
        print(f"  upload failed for {key}: {error}", file=sys.stderr)
        return False


# ── Main ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["sync"])
    parser.add_argument("--out", required=True, help="directory for rendered cards")
    parser.add_argument("--all", action="store_true", help="ignore the manifest, render everything")
    parser.add_argument("--limit", type=int, default=0, help="render at most N (for testing)")
    parser.add_argument("--no-upload", action="store_true")
    parser.add_argument("--wrangler", action="store_true", help="upload with wrangler (local OAuth)")
    parser.add_argument("--endpoint", help="CMS og-put endpoint")
    parser.add_argument("--token", help="shared secret for the endpoint")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    records = collect()
    print(f"{len(records)} cards belong on R2")

    manifest = {} if args.all else remote_manifest()

    with cf.ThreadPoolExecutor(max_workers=12) as pool:
        stamps = dict(zip((r["key"] for r in records),
                          pool.map(lambda r: image_stamp(r["image"]), records)))

    todo = []
    fresh_manifest = dict(manifest)
    for record in records:
        stamp = stamps[record["key"]]
        if stamp == "missing":
            continue
        digest = input_hash(record, stamp)
        if manifest.get(record["key"]) != digest:
            todo.append((record, digest))
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} to render")

    def build(item):
        record, digest = item
        image = load_image(record["image"])
        if image is None:
            return record["key"], None
        card = render_card(record, image)
        filename = os.path.join(args.out, record["key"].replace("/", "__"))
        card.save(filename, "JPEG", quality=87, progressive=True)
        return record["key"], (digest, filename)

    rendered: list[tuple[str, str, str]] = []
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for key, result in pool.map(build, todo):
            if result:
                rendered.append((key, result[0], result[1]))
    print(f"{len(rendered)} rendered")

    if args.no_upload or not rendered:
        for key, digest, _ in rendered:
            fresh_manifest[key] = digest
        if not args.no_upload:
            print("nothing to upload")
        return 0

    uploaded = 0
    for key, digest, path in rendered:
        ok = (
            put_wrangler(key, path)
            if args.wrangler
            else put_endpoint(args.endpoint, args.token or "", key, path)
        )
        if ok:
            uploaded += 1
            fresh_manifest[key] = digest
        else:
            print(f"  FAILED {key}", file=sys.stderr)

    manifest_path = os.path.join(args.out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(fresh_manifest, handle)
    manifest_ok = (
        put_wrangler("og/manifest.json", manifest_path)
        if args.wrangler
        else put_endpoint(args.endpoint, args.token or "", "og/manifest.json", manifest_path)
    )
    print(f"uploaded {uploaded}/{len(rendered)} cards, manifest {'ok' if manifest_ok else 'FAILED'}")
    return 0 if uploaded == len(rendered) and manifest_ok else 1


if __name__ == "__main__":
    sys.exit(main())
