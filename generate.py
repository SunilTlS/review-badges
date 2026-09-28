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


def fetch_stats(store: str) -> tuple:
    """Return (count, rating) from the storefront JSON page. Env overrides are for local test runs."""
    c_env = os.environ.get(f"BADGE_COUNT_{store.upper()}")
    r_env = os.environ.get(f"BADGE_RATING_{store.upper()}")
    if c_env:
        return int(c_env), float(r_env or 5)
    data = json.loads(http_get(STORES[store] + COUNT_PATH).decode("utf-8", "ignore").strip())
    count = int(data["count"])
    rating = float(data.get("rating") or 0)
    if count <= 0:
        raise ValueError("count is zero")
    return count, rating


def render_badge(count: int, lang: str, scale: int) -> Image.Image:
    base = Image.open(os.path.join(ASSETS, f"badge-{lang}.png")).convert("RGBA")
    if scale != 1:
        base = base.resize((BASE_W * scale, BASE_H * scale), Image.LANCZOS)
    text = str(count)
    size = (FONT_SIZE_6_DIGITS if len(text) > 5 else FONT_SIZE_5_DIGITS) * scale
    font = ImageFont.truetype(FONT_PATH, size)
    ImageDraw.Draw(base).text((TEXT_X * scale, TEXT_BASELINE * scale), text, font=font, fill=(255, 255, 255, 255), anchor="ms")
    return base


# ---- Rating badge: "4.4  ★★★★☆  Based on 36342 customer reviews" ----
RATING_W, RATING_H = 320, 56
STAR_GOLD = (255, 196, 0, 255)
TEXT_DARK = (34, 34, 34, 255)
RATING_TEXT = {
    "en": "Based on {n} customer reviews",
    "es": "Basado en {n} reseñas de clientes",
}


def _star_points(cx: float, cy: float, r_out: float, r_in: float) -> list:
    import math
    pts = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(-90 + i * 36)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def render_rating(count: int, rating: float, lang: str, scale: int) -> Image.Image:
    ss = 4 * scale                                   # draw 4x larger, then downsample for smooth edges
    w, h = RATING_W * ss, RATING_H * ss
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    rating = max(0.0, min(5.0, round(rating, 1)))
    draw.text((12 * ss, 44 * ss), f"{rating:.1f}", font=ImageFont.truetype(FONT_PATH, 38 * ss), fill=TEXT_DARK, anchor="ls")

    star_r, gap, x0, cy = 13, 3, 84, 19             # outer radius, spacing, first star left edge, centre line (1x units)
    for i in range(5):
        cx = (x0 + star_r + i * (2 * star_r + gap)) * ss
        pts = _star_points(cx, cy * ss, star_r * ss, star_r * 0.45 * ss)
        fill = max(0.0, min(1.0, rating - i))       # 1 = full star, 0.4 = 40% filled, 0 = empty
        if fill > 0:
            mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(mask).polygon(pts, fill=255)
            clip = Image.new("L", (w, h), 0)
            left = cx - star_r * ss
            ImageDraw.Draw(clip).rectangle([left, 0, left + fill * 2 * star_r * ss, h], fill=255)
            from PIL import ImageChops
            img.paste(STAR_GOLD, (0, 0), ImageChops.multiply(mask, clip))
        draw.polygon(pts, outline=STAR_GOLD, width=max(1, int(1.6 * ss)))

    label = RATING_TEXT[lang].format(n=count)
    draw.text((x0 * ss, 49 * ss), label, font=ImageFont.truetype(FONT_PATH, 12 * ss), fill=TEXT_DARK, anchor="ls")

    return img.resize((RATING_W * scale, RATING_H * scale), Image.LANCZOS)


def rating_file_name(store: str, lang: str, scale: int) -> str:
    return f"rating-reviews-{store}{'-es' if lang == 'es' else ''}{'@2x' if scale == 2 else ''}.png"


def all_names(store: str) -> list:
    return [fn(store, l, sc) for fn in (file_name, rating_file_name) for l in LANGS for sc in SCALES]


def file_name(store: str, lang: str, scale: int) -> str:
    return f"verified-reviews-{store}{'-es' if lang == 'es' else ''}{'@2x' if scale == 2 else ''}.png"


def keep_previous(store: str) -> bool:
    """Download the currently published images for this store so they stay online."""
    if not PUBLISHED_BASE:
        return False
    ok = True
    for name in all_names(store):
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
            count, rating = fetch_stats(store)
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
                rname = rating_file_name(store, lang, scale)
                render_rating(count, rating, lang, scale).convert("RGB").save(os.path.join(OUT, rname), format="PNG", optimize=True)
                print(f"  wrote {rname}")
        report["stores"][store] = {"status": "ok", "count": count, "rating": rating}

    with open(os.path.join(OUT, "counts.json"), "w") as fh:
        json.dump(report, fh, indent=2)

    cards = "".join(
        f'<figure><img src="{n}" alt="{n}" style="max-width:100%"><figcaption><a href="{n}">{n}</a></figcaption></figure>'
        for s in ENABLED for n in all_names(s)
    )
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(
            "<!doctype html><meta charset='utf-8'><title>Review badges</title>"
            "<style>body{font:14px Arial;margin:24px}figure{display:inline-block;margin:12px;vertical-align:top;text-align:center}</style>"
            f"<h1>Review badges</h1><p>Generated {report['generated_at']}</p>{cards}"
        )

    if failures:
        print(f"no image available for: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
