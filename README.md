# Judge.me review badge, scheduled static images

Once a day a GitHub Actions job draws the current Judge.me review count onto the
"VERIFIED REVIEWS" badge artwork and publishes the PNGs to GitHub Pages at fixed
URLs. Emails reference those URLs. No server, no API keys.

Published files (replace `<pages-url>` with the URL GitHub Pages gives the repo):

```
<pages-url>/verified-reviews-us.png          English, 228x166
<pages-url>/verified-reviews-us@2x.png       English, 456x332 (retina)
<pages-url>/verified-reviews-us-es.png       Spanish ribbon
<pages-url>/verified-reviews-us-es@2x.png
... same pattern for au, ca, eu
<pages-url>/counts.json                      what was rendered and when
```

## How it works

1. Each storefront publishes its count at `/pages/review-count` (theme template
   `page.review-count.liquid`, printing `{"count": N}` from the Judge.me shop metafield).
2. `generate.py` reads it for every store, draws the number on `assets/badge-en.png`
   or `assets/badge-es.png` with `assets/OpenSans-Regular.ttf`, and writes `public/`.
3. The workflow uploads `public/` to GitHub Pages. If a storefront cannot be read,
   that store's previously published images are kept so nothing breaks.

## Files

```
generate.py                      the generator
.github/workflows/badges.yml     daily schedule + Pages deploy (actions pinned by SHA)
assets/                          artwork (EN, ES), font and its OFL licence
requirements.txt                 Pillow, pinned
```

## Run locally

```
pip install Pillow==12.2.0
BADGE_COUNT_US=36212 python generate.py     # forces a number; omit to read the live page
```

Output lands in `public/`.

## Hosting elsewhere

Everything Pages-specific is the last two steps of the workflow. To publish to S3 or
Cloudflare R2 instead, replace them with an upload step and set `BADGE_PUBLISHED_BASE`
to that bucket's public URL so the keep-previous fallback still works.
"# review-badges" 
