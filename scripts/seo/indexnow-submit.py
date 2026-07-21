#!/usr/bin/env python3
"""Submit site URLs to IndexNow (Bing, Seznam, Naver, Yandex — and the index
behind Microsoft Copilot citations).

The key is hosted at https://indianliberals.in/8857e84b5745431fb0913015ce306fe6.txt
(apps/site/public/). Search engines verify ownership by fetching it.

Usage:
    python3 scripts/seo/indexnow-submit.py                  # whole sitemap
    python3 scripts/seo/indexnow-submit.py URL [URL ...]    # specific pages

Run after deploys that add or materially change pages. Re-submitting
unchanged URLs is harmless (engines dedupe) but rate-limited, so prefer
passing just the changed URLs during ingestion loops.
"""
import json
import sys
import re
import urllib.request

KEY = "8857e84b5745431fb0913015ce306fe6"
HOST = "indianliberals.in"
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10000  # protocol max per POST


def sitemap_urls():
    req = urllib.request.Request(
        f"https://{HOST}/sitemap-0.xml", headers={"User-Agent": "Mozilla/5.0"})
    xml = urllib.request.urlopen(req, timeout=60).read().decode()
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def submit(urls):
    body = json.dumps({
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": urls,
    }).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status


def main():
    urls = sys.argv[1:] or sitemap_urls()
    print(f"submitting {len(urls)} URLs to IndexNow")
    for i in range(0, len(urls), BATCH):
        status = submit(urls[i:i + BATCH])
        print(f"  batch {i // BATCH + 1}: HTTP {status}")


if __name__ == "__main__":
    main()
