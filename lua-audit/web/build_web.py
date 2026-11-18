#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_web.py — از قالب وب، فایل تک‌فایلی آفلاین می‌سازد.

ورودی :  web/index.template.html   (جای‌نگهدارهای __SPLASH__ و __LOGO__)
         ../assets/splash.png ، ../assets/logo.png
خروجی :  web/SskidScanner.html     (تک‌فایل، آفلاین، قابل باز شدن روی هر مرورگر)

اجرا:  python -X utf8 build_web.py
"""

import base64
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), 'assets')
TEMPLATE = os.path.join(HERE, 'index.template.html')
OUT = os.path.join(HERE, 'SskidScanner.html')


def data_uri(path):
    with open(path, 'rb') as f:
        raw = f.read()
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'webp': 'image/webp', 'gif': 'image/gif', 'ico': 'image/x-icon'}.get(ext, 'image/png')
    return 'data:%s;base64,%s' % (mime, base64.b64encode(raw).decode('ascii'))


def main():
    if not os.path.exists(TEMPLATE):
        print('template not found:', TEMPLATE)
        return 2
    splash = os.path.join(ASSETS, 'splash.png')
    logo = os.path.join(ASSETS, 'logo.png')
    if not os.path.exists(splash):
        print('missing', splash, '- run make_assets.py first')
        return 2

    html = open(TEMPLATE, encoding='utf-8').read()
    html = html.replace('__SPLASH__', data_uri(splash))
    html = html.replace('__LOGO__', data_uri(logo if os.path.exists(logo) else splash))

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print('wrote', OUT, '(%s bytes)' % f'{os.path.getsize(OUT):,}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
