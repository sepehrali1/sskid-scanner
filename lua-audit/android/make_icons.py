#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_icons.py — از assets/logo.png (یا icon.ico) آیکون‌های لانچر اندروید می‌سازد.

خروجی:
    android/app/src/main/res/mipmap-mdpi/ic_launcher.png      (48x48)
    android/app/src/main/res/mipmap-hdpi/ic_launcher.png      (72x72)
    android/app/src/main/res/mipmap-xhdpi/ic_launcher.png     (96x96)
    android/app/src/main/res/mipmap-xxhdpi/ic_launcher.png    (144x144)
    android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png   (192x192)

اجرا:  python -X utf8 android/make_icons.py
"""

import os
import sys

try:
    from PIL import Image
except ImportError:
    print('Pillow لازم است:  pip install pillow')
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))          # .../lua-audit/android
ROOT = os.path.dirname(HERE)                               # .../lua-audit
ASSETS = os.path.join(ROOT, 'assets')
RES = os.path.join(HERE, 'app', 'src', 'main', 'res')

SIZES = {
    'mipmap-mdpi': 48,
    'mipmap-hdpi': 72,
    'mipmap-xhdpi': 96,
    'mipmap-xxhdpi': 144,
    'mipmap-xxxhdpi': 192,
}


def find_source():
    for name in ('logo.png', 'splash.png', 'icon.ico'):
        p = os.path.join(ASSETS, name)
        if os.path.exists(p):
            return p
    return None


def main():
    src = find_source()
    if not src:
        print('منبع آیکون پیدا نشد. اول make_assets.py را اجرا کن (assets/logo.png).')
        return 2
    print('source:', src)
    base = Image.open(src).convert('RGBA')

    # مربع کردن با حفظ نسبت
    w, h = base.size
    side = max(w, h)
    canvas = Image.new('RGBA', (side, side), (7, 7, 11, 255))
    canvas.paste(base, ((side - w) // 2, (side - h) // 2), base)

    for folder, px in SIZES.items():
        out_dir = os.path.join(RES, folder)
        os.makedirs(out_dir, exist_ok=True)
        img = canvas.resize((px, px), Image.LANCZOS)
        dst = os.path.join(out_dir, 'ic_launcher.png')
        img.save(dst, 'PNG')
        print('  %-18s %3dx%-3d  %s' % (folder, px, px, os.path.relpath(dst, ROOT)))
    print('آیکون‌ها ساخته شدند.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
