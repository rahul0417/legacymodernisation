"""Compose side-by-side mosaic from the 16 dual-run screenshots.

Pairs each `old-NN-*.png` with the matching `new-NN-*.png` into a stacked
horizontal panel, labels each side, then stacks all 8 pairs vertically.

Output: `screenshots/mosaic.png` — one composite image suitable for
embedding in the cockpit or a pitch deck.

Run from anywhere — paths are derived relative to this script.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
SCREEN_DIR = HERE.parent / "screenshots"
OUT = SCREEN_DIR / "mosaic.png"

PAIRS = [
    ("old-01-list.png",            "new-01-list.png",            "List view"),
    ("old-02-add-form.png",        "new-02-add-modal.png",       "Add new user"),
    ("old-03-edit-form-id1.png",   "new-04-edit-modal.png",      "Edit existing user"),
    ("old-04-edit-missing-id.png", "new-03-add-validation-error.png", "Missing data / validation"),
    ("old-05-delete-hover.png",    "new-06-delete-alert.png",    "Delete confirmation"),
    ("old-06-add-action-success.png", "new-05-edit-email-conflict.png", "Server response surface"),
    ("old-07-list-narrow.png",     "new-08-empty-state.png",     "Edge / empty state"),
    ("old-08-edit-form-id2.png",   "new-07-loading-skeleton.png", "Edit / loading"),
]

# Layout constants
PAIR_HEIGHT = 360        # each side scaled to this height before placement
PAD = 12
LABEL_H = 34
HEADER_H = 60
SIDE_LABEL = ("Legacy · chapagain/crud-php-simple", "Modern · FastAPI + React/shadcn")
BG = (245, 246, 248)
LABEL_BG_LEGACY = (250, 224, 200)   # peach
LABEL_BG_NEW = (210, 240, 220)      # mint
LABEL_FG = (24, 28, 32)
HEADER_FG = (24, 28, 32)


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def fit(img: Image.Image, target_h: int) -> Image.Image:
    w, h = img.size
    new_w = int(w * (target_h / h))
    return img.resize((new_w, target_h), Image.LANCZOS)


def main() -> int:
    if not SCREEN_DIR.exists():
        print(f"[mosaic] screenshots dir missing: {SCREEN_DIR}", file=sys.stderr)
        return 2

    cells: list[tuple[Image.Image, Image.Image, str]] = []
    max_pair_w = 0
    for old_name, new_name, label in PAIRS:
        old_p = SCREEN_DIR / old_name
        new_p = SCREEN_DIR / new_name
        if not old_p.exists() or not new_p.exists():
            print(f"[mosaic] missing pair {old_name} / {new_name}, skipping", file=sys.stderr)
            continue
        old_img = fit(Image.open(old_p).convert("RGB"), PAIR_HEIGHT)
        new_img = fit(Image.open(new_p).convert("RGB"), PAIR_HEIGHT)
        pair_w = old_img.width + new_img.width + PAD
        max_pair_w = max(max_pair_w, pair_w)
        cells.append((old_img, new_img, label))

    if not cells:
        print("[mosaic] no pairs captured", file=sys.stderr)
        return 1

    canvas_w = max_pair_w + PAD * 2
    canvas_h = HEADER_H + (PAIR_HEIGHT + LABEL_H + PAD) * len(cells) + PAD
    canvas = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(canvas)

    title_font = load_font(22)
    side_font = load_font(13)
    label_font = load_font(15)

    draw.text(
        (PAD, 18),
        "MWU-CRUD-001 · Visual Transformation · legacy chapagain ↔ React/shadcn",
        fill=HEADER_FG,
        font=title_font,
    )

    y = HEADER_H
    for (old_img, new_img, label) in cells:
        legacy_w = old_img.width
        new_w = new_img.width
        # label strip
        draw.rectangle((PAD, y, PAD + legacy_w, y + LABEL_H), fill=LABEL_BG_LEGACY)
        draw.rectangle(
            (PAD + legacy_w + PAD, y, PAD + legacy_w + PAD + new_w, y + LABEL_H),
            fill=LABEL_BG_NEW,
        )
        draw.text((PAD + 8, y + 7), f"↓ LEGACY · {SIDE_LABEL[0]}", fill=LABEL_FG, font=side_font)
        draw.text(
            (PAD + legacy_w + PAD + 8, y + 7),
            f"↑ MODERN · {SIDE_LABEL[1]}",
            fill=LABEL_FG,
            font=side_font,
        )
        # scenario label aligned right
        draw.text(
            (canvas_w - PAD - 220, y + 9),
            label,
            fill=LABEL_FG,
            font=label_font,
        )
        # images
        canvas.paste(old_img, (PAD, y + LABEL_H))
        canvas.paste(new_img, (PAD + legacy_w + PAD, y + LABEL_H))
        y += LABEL_H + PAIR_HEIGHT + PAD

    canvas.save(OUT, format="PNG", optimize=True)
    print(f"[mosaic] wrote {OUT} ({canvas.size[0]}×{canvas.size[1]}, {len(cells)} pairs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
