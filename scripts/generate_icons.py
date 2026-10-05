"""Generate the PWA icons for the frontend (run with the backend venv, which has Pillow).

    backend\\.venv\\Scripts\\python.exe scripts\\generate_icons.py

Writes frontend/public/icons/icon-192.png, icon-512.png and icon-maskable-512.png.
The icon is a simple generated mark (blue square, white "E" and chip pins) - replace
with the official brand artwork when available.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "icons"
BLUE = (37, 99, 235, 255)
WHITE = (255, 255, 255, 255)


def draw_icon(size: int, maskable: bool) -> Image.Image:
    img = Image.new("RGBA", (size, size), BLUE if maskable else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Maskable icons keep content inside the central 80% safe zone.
    pad = int(size * (0.2 if maskable else 0.06))
    if not maskable:
        d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=int(size * 0.18), fill=BLUE)
    inner = size - 2 * pad
    # Chip pins
    pin_w, pin_l = max(2, inner // 22), max(3, inner // 12)
    for i in range(4):
        y = pad + int(inner * (0.28 + i * 0.15))
        d.rectangle([pad + int(inner * 0.12), y, pad + int(inner * 0.12) + pin_l, y + pin_w], fill=WHITE)
        d.rectangle([size - pad - int(inner * 0.12) - pin_l, y, size - pad - int(inner * 0.12), y + pin_w], fill=WHITE)
    # Letter E built from rectangles (no font dependency)
    x0, x1 = pad + int(inner * 0.34), pad + int(inner * 0.68)
    y0, y1 = pad + int(inner * 0.24), pad + int(inner * 0.76)
    bar = max(3, int(inner * 0.09))
    d.rectangle([x0, y0, x0 + bar, y1], fill=WHITE)
    d.rectangle([x0, y0, x1, y0 + bar], fill=WHITE)
    mid = (y0 + y1) // 2 - bar // 2
    d.rectangle([x0, mid, x1 - int(inner * 0.05), mid + bar], fill=WHITE)
    d.rectangle([x0, y1 - bar, x1, y1], fill=WHITE)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    draw_icon(192, False).save(OUT / "icon-192.png")
    draw_icon(512, False).save(OUT / "icon-512.png")
    draw_icon(512, True).save(OUT / "icon-maskable-512.png")
    draw_icon(180, True).convert("RGB").save(OUT / "apple-touch-icon.png")
    print(f"Icons written to {OUT}")


if __name__ == "__main__":
    main()
