# -*- coding: utf-8 -*-
"""
make_assets.py — از عکس ورودی، دارایی‌های برنامه را می‌سازد:
    assets/splash.png   عکس اسپلش (کوچک‌شده، برای پنجرهٔ لودینگ)
    assets/logo.png     لوگوی کوچک (نوار بالا و سایدبار)
    assets/icon.ico     آیکون ویندوز برای exe
و پالت رنگی غالب عکس را چاپ می‌کند تا تم برنامه از خود عکس دربیاید.

اجرا:  python -X utf8 make_assets.py "C:\\path\\to\\image.webp"
"""

import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
os.makedirs(ASSETS, exist_ok=True)


def dominant_colors(img, count=8, sample=200):
    """رنگ‌های غالب را برمی‌گرداند (با کوانتیزه کردن برای سرعت)."""
    small = img.convert('RGB').resize((sample, sample))
    q = small.quantize(colors=count, method=Image.MEDIANCUT).convert('RGB')
    total = sum(n for n, _ in q.getcolors(sample * sample) or [])
    out = []
    for n, rgb in sorted(q.getcolors(sample * sample) or [], reverse=True):
        out.append((rgb, n / max(1, total)))
    return out


def hexof(rgb):
    return '#%02x%02x%02x' % rgb


def luminance(rgb):
    r, g, b = rgb
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def boost(rgb, factor=1.35):
    return tuple(min(255, int(c * factor)) for c in rgb)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.expanduser('~'), 'Downloads', 'noFilter.webp')
    if not os.path.exists(src):
        print('image not found:', src)
        return 2

    img = Image.open(src)
    print('source      :', src)
    print('size        :', img.size, ' mode:', img.mode)

    rgb = img.convert('RGB')

    # --- اسپلش: حداکثر عرض 460، حداکثر ارتفاع 220
    w, h = rgb.size
    scale = min(460 / w, 220 / h, 1.0)
    sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
    splash = rgb.resize((sw, sh), Image.LANCZOS)
    splash.save(os.path.join(ASSETS, 'splash.png'))
    print('splash.png  :', (sw, sh))

    # --- لوگو: مربع 96px، برش مرکزی
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    logo = rgb.crop((left, top, left + side, top + side)).resize((96, 96), Image.LANCZOS)
    logo.save(os.path.join(ASSETS, 'logo.png'))
    print('logo.png    : 96x96')

    # --- آیکون ویندوز
    ico = rgb.copy()
    ico.thumbnail((256, 256), Image.LANCZOS)
    ico.save(os.path.join(ASSETS, 'icon.ico'),
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('icon.ico    : ok')

    # --- پالت
    print('\ndominant colors (share, luminance):')
    cols = dominant_colors(rgb, count=8)
    for rgbc, share in cols:
        print('  %s  %5.1f%%  lum=%.2f' % (hexof(rgbc), share * 100, luminance(rgbc)))

    dark = [c for c, s in cols if luminance(c) < 0.35]
    bright = [c for c, s in cols if luminance(c) >= 0.35]
    print('\nsuggested palette:')
    if dark:
        bg = min(dark, key=luminance)
        print('  BG      ', hexof(bg))
        print('  PANEL   ', hexof(boost(bg, 1.6)))
        print('  PANEL2  ', hexof(boost(bg, 2.1)))
    if bright:
        accent = max(bright, key=lambda c: max(c) - min(c))  # پررنگ‌ترین/اشباع‌ترین
        print('  ACCENT  ', hexof(accent))
    return 0


if __name__ == '__main__':
    sys.exit(main())
