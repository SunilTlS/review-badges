"""
Judge.me "Verified Reviews" badge - scheduled static image generator - Sep 28 2026 - Sunil

Run once a day (GitHub Actions, see .github/workflows/badges.yml). For every store,
language and scale it draws the current Judge.me review count onto the badge artwork
and writes a PNG into public/, which the workflow publishes to GitHub Pages at a
fixed URL. Emails reference those fixed URLs.

Output files (public/):
    verified-reviews-us.png          English, 228x166
    verified-reviews-us@2x.png       English, 456x332 (retina)
    verified-reviews-us-es.png       Spanish ribbon
    verified-reviews-us-es@2x.png
    ... same for au, ca, eu
    counts.json                      what was rendered and when

Count source: the store's own /pages/review-count page (theme template
page.review-count.liquid), which prints {"count": N} from the Judge.me shop metafield.

If a store cannot be read, its previously published images are downloaded from
BADGE_PUBLISHED_BASE and kept, so a storefront hiccup never leaves a broken image.
For a one-off local run you can force a number with BADGE_COUNT_US=36212 etc.
"""

import json
import os
import sys
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "public")
FONT_PATH = os.path.join(ASSETS, "OpenSans-Regular.ttf")

STORES = {
    "us": "https://theayurvedaexperience.com",
}
# Only build these stores (comma list). Add a store here once its /pages/review-count page exists.
ENABLED = [s.strip() for s in os.environ.get("BADGE_STORES", "us").split(",") if s.strip() in STORES]
COUNT_PATH = "/pages/review-count"
LANGS = ("en", "es")
SCALES = (1, 2)

BASE_W, BASE_H = 228, 166
TEXT_X, TEXT_BASELINE = 115, 80
FONT_SIZE_5_DIGITS = 38
FONT_SIZE_6_DIGITS = 32
FETCH_TIMEOUT = 15

# Where the images are already published; used to keep the previous image on failure.
PUBLISHED_BASE = os.environ.get("BADGE_PUBLISHED_BASE", "").rstrip("/")


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "TAE-ReviewBadge/1.0 (+scheduled badge generator)"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        return resp.read()


def fetch_count(store: str) -> int:
    override = os.environ.get(f"BADGE_COUNT_{store.upper()}")
    if override:
        return int(override)
    body = http_get(STORES[store] + COUNT_PATH).decode("utf-8", "ignore").strip()
    count = int(json.loads(body)["count"])
    if count <= 0:
        raise ValueError("count is zero")
    return count


def render_badge(count: int, lang: str, scale: int) -> Image.Image:
    base = Image.open(os.path.join(ASSETS, f"badge-{lang}.png")).convert("RGBA")
    if scale != 1:
        base = base.resize((BASE_W * scale, BASE_H * scale), Image.LANCZOS)
    text = str(count)
    size = (FONT_SIZE_6_DIGITS if len(text) > 5 else FONT_SIZE_5_DIGITS) * scale
    font = ImageFont.truetype(FONT_PATH, size)
    ImageDraw.Draw(base).text((TEXT_X * scale, TEXT_BASELINE * scale), text, font=font, fill=(255, 255, 255, 255), anchor="ms")
    return base


def file_name(store: str, lang: str, scale: int) -> str:
    return f"verified-reviews-{store}{'-es' if lang == 'es' else ''}{'@2x' if scale == 2 else ''}.png"


def keep_previous(store: str) -> bool:
    """Download the currently published images for this store so they stay online."""
    if not PUBLISHED_BASE:
        return False
    ok = True
    for lang in LANGS:
        for scale in SCALES:
            name = file_name(store, lang, scale)
            try:
                data = http_get(f"{PUBLISHED_BASE}/{name}")
                with open(os.path.join(OUT, name), "wb") as fh:
                    fh.write(data)
                print(f"  kept previous {name}")
            except Exception as exc:
                print(f"  could not keep previous {name}: {exc}")
                ok = False
    return ok


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stores": {}}
    failures = []

    for store in ENABLED:
        print(f"[{store}]")
        try:
            count = fetch_count(store)
        except Exception as exc:
            print(f"  count unavailable ({exc})")
            report["stores"][store] = {"status": "kept-previous" if keep_previous(store) else "missing"}
            if report["stores"][store]["status"] == "missing":
                failures.append(store)
            continue

        for lang in LANGS:
            for scale in SCALES:
                name = file_name(store, lang, scale)
                render_badge(count, lang, scale).save(os.path.join(OUT, name), format="PNG", optimize=True)
                print(f"  wrote {name}")
        report["stores"][store] = {"status": "ok", "count": count}

    with open(os.path.join(OUT, "counts.json"), "w") as fh:
        json.dump(report, fh, indent=2)

    links = "".join(
        f'<li><a href="{file_name(s, l, sc)}">{file_name(s, l, sc)}</a></li>'
        for s in ENABLED for l in LANGS for sc in SCALES
    )
    with open(os.path.join(OUT, "index.html"), "w") as fh:
        fh.write(f"<!doctype html><title>Review badges</title><h1>Review badges</h1><p>Generated {report['generated_at']}</p><ul>{links}</ul>")

    if failures:
        print(f"no image available for: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
