#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lua_audit.py — جعبه‌ابزار بازرسی استاتیک فایل‌های Lua/Luau
============================================================
هیچ فایلی را اجرا نمی‌کند. فقط بایت‌ها را می‌خواند.

دستورها:
    python lua_audit.py hash   <file>
    python lua_audit.py scan   <file> [--json]
    python lua_audit.py urls   <file|dir>
    python lua_audit.py batch  <dir> [--min-score N]
    python lua_audit.py watch  [--known known.json]

نمونه:
    python lua_audit.py scan suspicious.lua
    python lua_audit.py batch ./scripts --min-score 40
    python lua_audit.py watch
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict

# ---------------------------------------------------------------- ثابت‌ها

BIN_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp3', '.ogg', '.wav',
           '.mp4', '.webm', '.rbxm', '.rbxmx', '.ttf', '.otf', '.zip', '.exe', '.dll'}

# (کد، الگو، نوع، وزن، توضیح)
# نوع threat    = نشانهٔ آسیب/دزدی/پنهان‌کاری
# نوع capability = قدرتِ خنثی (ابزارهای مشروع هم دارند)
RULES = [
    ('remote_exec',   r'loadstring\s*\(\s*(?:game\s*:\s*HttpGet|httpget|request)', 'threat', 55,
     'code is downloaded and executed at runtime'),
    ('http_get',      r'\bgame\s*:\s*HttpGet\b|\bhttpget\s*\(', 'capability', 12,
     'fetches a remote file'),
    ('http_request',  r'\bhttp_request\b|\bsyn\s*\.\s*request\b|\bfluxus\s*\.\s*request\b',
     'capability', 10, 'raw HTTP capability'),
    ('webhook',       r'discord(?:app)?\.com/api/webhooks/', 'threat', 50,
     'posts to a Discord webhook'),
    ('ip_lookup',     r'icanhazip|ipify|ipinfo\.io|whatismyip|checkip\.amazonaws', 'threat', 25,
     'resolves the public IP address'),
    ('clipboard',     r'\b(?:setclipboard|toclipboard|getclipboard)\b', 'capability', 10,
     'reads or writes the clipboard'),
    ('file_write',    r'\b(?:writefile|appendfile|delfile|makefolder)\s*\(', 'capability', 10,
     'writes to the local filesystem'),
    ('file_read',     r'\b(?:readfile|listfiles|isfile)\s*\(', 'capability', 6,
     'reads the local filesystem'),
    ('kick',          r'[:.]\s*Kick\s*\(', 'threat', 25, 'kicks the local player'),
    ('anti_tamper',   r'Tamper Detected|anti[-_ ]?tamper|debugInfo\s*=\s*false', 'threat', 20,
     'anti-tamper / hides its own traces'),
    ('getgenv',       r'\bgetgenv\s*\(|\bgetrenv\s*\(|\bgethui\s*\(', 'capability', 6,
     'touches executor globals'),
    ('hook',          r'\bhookfunction\b|\bhookmetamethod\b|\bsetreadonly\b', 'capability', 10,
     'hooks engine functions'),
    ('remote_call',   r'\bFireServer\s*\(|\bInvokeServer\s*\(', 'capability', 4,
     'invokes remote events'),
    ('identity',      r'\bidentifyexecutor\s*\(|\bgetcustomasset\b', 'capability', 4,
     'fingerprints the executor'),
    ('decoy_print',   r'print\s*\(\s*["\'](?:Hello World|Hello Nigga)["\']\s*\)', 'capability', 0,
     'known decoy payload (does nothing)'),
    ('long_loop',     r'while\s+true\s+do\s*$', 'threat', 10, 'infinite loop (client freeze)'),
    ('fake_auth',     r'_G\.(?:AUTH_KEY|AUTHORIZED_SOURCE)|AUTHORIZED_SOURCE\s*=', 'capability', 6,
     'placebo auth globals (checked by nothing)'),
]

URL_RE = re.compile(r'https?://[^\s"\'<>\)\]\}\,]+', re.I)
WEBHOOK_RE = re.compile(r'(discord(?:app)?\.com/api/webhooks/\d+/)([A-Za-z0-9_\-]+)', re.I)

OBF_SIGNATURES = [
    ('WeAreDevs', r'wearedevs\.net/obfuscator'),
    ('Luraph',    r'Luraph|LPH!'),
    ('PSU',       r'psu\.dev|psu\.gg'),
    ('MoonSec',   r'monsec|moonsec'),
    ('Ironbrew',  r'ironbrew|ironbrew2'),
    ('generic-VM', r'\breturn\s*\(function\(\.\.\.\)\s*local\s+\w+\s*=\s*\{'),
]

# بسته‌بندهایی که کد را واقعاً پنهان می‌کنند (نه فقط فشرده‌سازی خوش‌خیم)
HIDING_PACKERS = {'WeAreDevs', 'Luraph', 'PSU', 'MoonSec', 'Ironbrew'}

KNOWN_DEFAULT = {
    'script689': {
        'size': 21,
        'sha256': 'db63149bd0e2e4fa2f3446dba3074805e9e84b313fbd73bfa1c11eeaa9a70952',
        'url': 'https://raw.githubusercontent.com/ermiya1231/Script1/refs/heads/main/script689',
    },
    'sskidiswhite': {
        'size': 21,
        'sha256': '227e1ead641358da822810e4c62a311c75a1165ee3a2126dfa6e93613b335384',
        'url': 'https://raw.githubusercontent.com/ermiya1231/Script1/refs/heads/main/sskidiswhite',
    },
}

# ---------------------------------------------------------------- کمکی‌ها


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def entropy(data):
    """آنتروپی شانون بر حسب بیت/بایت. بالای ۷.۵ یعنی داده فشرده/رمزنگاری‌شده."""
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def printable_ratio(data):
    if not data:
        return 0.0
    return sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13)) / len(data)


def decode_text(data):
    for enc in ('utf-8', 'utf-8-sig', 'cp1256', 'latin-1'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', 'replace')


def mask_webhook(url):
    """دامنه و شناسه را نگه می‌دارد، توکن را می‌پوشاند."""
    m = WEBHOOK_RE.search(url)
    if not m:
        return url
    token = m.group(2)
    return '%s%s…%s' % (m.group(1), token[:6], token[-4:])


def detect_obfuscator(text):
    found = []
    for name, pattern in OBF_SIGNATURES:
        if re.search(pattern, text, re.I):
            found.append(name)
    return found


def longest_line(text):
    return max((len(line) for line in text.splitlines()), default=0)


# ---------------------------------------------------------------- اسکن


def scan_file(path):
    data = read_bytes(path)
    text = decode_text(data)
    result = OrderedDict()
    result['file'] = os.path.abspath(path)
    result['bytes'] = len(data)
    result['sha256'] = sha256(data)
    result['entropy'] = round(entropy(data), 3)
    result['printable_ratio'] = round(printable_ratio(data), 3)
    result['longest_line'] = longest_line(text)
    result['obfuscators'] = detect_obfuscator(text)

    findings = []
    threat = 0
    capability = 0
    for code, pattern, kind, weight, note in RULES:
        matches = re.findall(pattern, text, re.I | re.M)
        if matches:
            if kind == 'threat':
                threat += weight
            else:
                capability += weight
            findings.append({'rule': code, 'kind': kind, 'hits': len(matches),
                             'weight': weight, 'note': note})

    # ---- قابل‌خواندن نبودن خودش یک یافته است ----
    # اگر کد بسته‌بندی شده باشد، هیچ‌کدام از الگوهای بالا نمی‌توانند داخلش را ببینند.
    # پس «چیزی پیدا نشد» به معنی «امن است» نیست؛ به معنی «نمی‌شود دید» است.
    packers = [o for o in result['obfuscators'] if o in HIDING_PACKERS]
    opaque = bool(packers)
    if opaque:
        threat += 25
        findings.append({'rule': 'packed', 'kind': 'threat', 'hits': len(packers), 'weight': 25,
                         'note': 'packed with %s — the code inside cannot be read statically'
                                 % ', '.join(packers)})

    if result['longest_line'] >= 20000:
        threat += 15
        findings.append({'rule': 'single_line', 'kind': 'threat', 'hits': 0, 'weight': 15,
                         'note': 'entire payload on one line (minified or packed)'})
    elif result['longest_line'] >= 4000:
        threat += 6
        findings.append({'rule': 'long_line', 'kind': 'threat', 'hits': 0, 'weight': 6,
                         'note': 'very long lines (generated or minified code)'})

    if result['bytes'] > 4096 and result['longest_line'] / result['bytes'] > 0.9:
        threat += 10
        findings.append({'rule': 'one_line_file', 'kind': 'threat', 'hits': 0, 'weight': 10,
                         'note': 'a single line covers almost the whole file'})

    esc = text.count('\\') / max(1, len(text))
    if esc > 0.02 and result['printable_ratio'] > 0.9:
        threat += 10
        findings.append({'rule': 'escape_heavy', 'kind': 'threat', 'hits': int(esc * 1000),
                         'weight': 10, 'note': 'heavy string escaping (obfuscation style)'})
    if result['entropy'] > 7.5:
        threat += 10
        findings.append({'rule': 'high_entropy', 'kind': 'threat', 'hits': 0, 'weight': 10,
                         'note': 'compressed or encrypted blob'})

    urls = sorted({u.rstrip('.,;') for u in URL_RE.findall(text)})
    result['urls'] = [mask_webhook(u) for u in urls]
    result['domains'] = sorted({re.sub(r'^https?://([^/]+).*$', r'\1', u).lower() for u in urls})
    result['webhook_count'] = sum(1 for u in urls if WEBHOOK_RE.search(u))

    score = min(100, threat + capability // 2)
    result['threat'] = threat
    result['capability'] = capability
    result['score'] = score
    result['auditable'] = not opaque
    result['verdict'] = ('DO NOT RUN' if score >= 60 else
                         'REVIEW' if score >= 25 else 'LOW RISK')
    result['findings'] = findings

    # آیا دقیقاً همان دکوی شناخته‌شده است؟
    result['known'] = None
    for name, meta in KNOWN_DEFAULT.items():
        if meta['sha256'] == result['sha256'] and meta['size'] == result['bytes']:
            result['known'] = name
    return result


def render_scan(r):
    out = []
    out.append('=' * 66)
    out.append('FILE      %s' % r['file'])
    out.append('SIZE      %s bytes' % f"{r['bytes']:,}")
    out.append('SHA256    %s' % r['sha256'])
    out.append('ENTROPY   %.3f bits/byte    PRINTABLE %.1f%%    LONGEST LINE %d'
               % (r['entropy'], r['printable_ratio'] * 100, r['longest_line']))
    out.append('OBFUSC.   %s' % (', '.join(r['obfuscators']) or 'none detected'))
    out.append('AUDITABLE %s' % ('no — packed, only metadata is visible'
                                 if not r.get('auditable', True) else 'yes'))
    if r.get('known'):
        out.append('KNOWN     exact match for "%s" (harmless decoy)' % r['known'])
    out.append('VERDICT   %s   (threat %d + capability %d/2 = %d/100)'
               % (r['verdict'], r.get('threat', 0), r.get('capability', 0), r['score']))
    out.append('')
    if not r.get('auditable', True):
        out.append('NOTE      "no findings" here does NOT mean "safe": the payload is packed,')
        out.append('          so the pattern scan cannot see inside it. Treat as unknown code.')
        out.append('')
    if r['findings']:
        out.append('FINDINGS')
        for f in r['findings']:
            tag = 'THREAT' if f.get('kind') == 'threat' else 'can   '
            out.append('  [%s] +%-14s x%-4d  %s' % (tag, f['rule'], f['hits'], f['note']))
    else:
        out.append('FINDINGS  none')
    if r['urls']:
        out.append('')
        out.append('URLS (%d, %d webhook)' % (len(r['urls']), r['webhook_count']))
        for u in r['urls'][:25]:
            out.append('  ' + u)
        if len(r['urls']) > 25:
            out.append('  ... %d more' % (len(r['urls']) - 25))
    out.append('')
    return '\n'.join(out)


def cmd_scan(args):
    r = scan_file(args.file)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(render_scan(r))
    return 1 if r['score'] >= 60 else 0


def cmd_hash(args):
    data = read_bytes(args.file)
    print('file    %s' % os.path.abspath(args.file))
    print('bytes   %s' % f'{len(data):,}')
    print('md5     %s' % hashlib.md5(data).hexdigest())
    print('sha1    %s' % hashlib.sha1(data).hexdigest())
    print('sha256  %s' % sha256(data))
    print('entropy %.3f' % entropy(data))


def decode_lua_escapes(s):
    """رشته‌های escape‌شدهٔ Lua را به متن برمی‌گرداند: \\ddd و \\xNN و \\n و ..."""
    def repl(m):
        tok = m.group(0)
        if tok[1] == 'x':
            return chr(int(tok[2:], 16))
        if tok[1].isdigit():
            return chr(int(tok[1:], 10) % 256)
        return {'n': '\n', 'r': '\r', 't': '\t', 'a': '\a', 'b': '\b',
                'f': '\f', 'v': '\v', '\\': '\\', '"': '"', "'": "'"}[tok[1]]
    return re.sub(r'\\x[0-9a-fA-F]{2}|\\\d{1,3}|\\[nrtabfv\\"\']', repl, s)


def cmd_strings(args):
    """رشته‌های خوانا را از داخل فایل بیرون می‌کشد (مثل strings در یونیکس) + دیکد escapeهای Lua."""
    data = read_bytes(args.target)
    n = max(2, args.min)
    found = []
    for m in re.finditer(rb'[\x20-\x7e]{%d,}' % n, data):
        found.append((m.start(), m.group().decode('ascii')))
    if args.escapes:
        text = decode_text(data)
        for m in re.finditer(r'(?:\\\d{1,3}|\\x[0-9a-fA-F]{2}|\\[nrtabfv\\"\']){3,}', text):
            dec = decode_lua_escapes(m.group())
            if len(dec) >= n and dec.isprintable():
                found.append((m.start(), dec))
    found.sort()
    seen, rows = set(), []
    for off, s in found:
        if args.grep and not re.search(args.grep, s, re.I):
            continue
        if s in seen:
            continue
        seen.add(s)
        rows.append((off, s))
        if len(rows) >= args.limit:
            break
    for off, s in rows:
        if len(s) > args.width:
            print('%08x  %s … [+%d chars]' % (off, s[:args.width], len(s) - args.width))
        else:
            print('%08x  %s' % (off, s))
    print('\n%d string(s)' % len(rows))


def cmd_urls(args):
    paths = []
    if os.path.isdir(args.target):
        for root, _, files in os.walk(args.target):
            for name in files:
                if os.path.splitext(name)[1].lower() not in BIN_EXT:
                    paths.append(os.path.join(root, name))
    else:
        paths.append(args.target)

    seen = {}
    for p in paths:
        try:
            text = decode_text(read_bytes(p))
        except OSError:
            continue
        for u in URL_RE.findall(text):
            seen.setdefault(u.rstrip('.,;'), set()).add(os.path.basename(p))

    print('%d unique URLs from %d files' % (len(seen), len(paths)))
    for u in sorted(seen):
        who = ', '.join(sorted(seen[u])[:3])
        print('  %s   <- %s' % (mask_webhook(u), who))


def cmd_batch(args):
    rows = []
    for root, _, files in os.walk(args.dir):
        for name in files:
            if os.path.splitext(name)[1].lower() in BIN_EXT:
                continue
            p = os.path.join(root, name)
            try:
                if os.path.getsize(p) > 5_000_000:
                    continue
                r = scan_file(p)
            except Exception:
                continue
            if r['score'] >= args.min_score:
                rows.append(r)
    rows.sort(key=lambda x: -x['score'])
    print('%-4s %-10s %-5s %-5s %-8s %s' % ('SCR', 'VERDICT', 'THR', 'CAP', 'BYTES', 'FILE'))
    for r in rows:
        print('%-4d %-10s %-5d %-5d %-8s %s'
              % (r['score'], r['verdict'], r.get('threat', 0), r.get('capability', 0),
                 r['bytes'], os.path.relpath(r['file'], args.dir)))
    print('\n%d file(s) at or above score %d' % (len(rows), args.min_score))


def cmd_watch(args):
    known = KNOWN_DEFAULT
    if args.known and os.path.exists(args.known):
        known = json.loads(open(args.known, encoding='utf-8').read())
    try:
        import urllib.request
    except ImportError:
        print('urllib unavailable')
        return 1

    changed = 0
    for name, meta in known.items():
        try:
            req = urllib.request.Request(meta['url'], headers={'User-Agent': 'lua-audit'})
            data = urllib.request.urlopen(req, timeout=30).read()
        except Exception as ex:
            print('[?] %-14s unreachable (%s)' % (name, ex))
            continue
        got = sha256(data)
        if got != meta['sha256']:
            changed += 1
            print('[!!] %-14s CHANGED  %d bytes  %s' % (name, len(data), got))
        else:
            print('[ok] %-14s same     %d bytes' % (name, len(data)))
    if changed:
        print('\n%d slot(s) changed: new code is queued for everyone who loads them.' % changed)
    return 1 if changed else 0


# ---------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='lua_audit',
        description='Static auditor for Lua/Luau scripts. Never executes the target.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('scan', help='full report for one file')
    p.add_argument('file')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser('hash', help='hashes and entropy')
    p.add_argument('file')
    p.set_defaults(func=cmd_hash)

    p = sub.add_parser('urls', help='extract URLs from a file or folder')
    p.add_argument('target')
    p.set_defaults(func=cmd_urls)

    p = sub.add_parser('strings', help='extract readable strings (and decode Lua escapes)')
    p.add_argument('target')
    p.add_argument('--min', type=int, default=4, help='minimum length (default 4)')
    p.add_argument('--grep', default=None, help='only strings matching this regex')
    p.add_argument('--no-escapes', dest='escapes', action='store_false',
                   help='skip decoding Lua escape sequences')
    p.add_argument('--limit', type=int, default=2000)
    p.add_argument('--width', type=int, default=240, help='truncate each printed string')
    p.set_defaults(func=cmd_strings)

    p = sub.add_parser('batch', help='scan a folder, sorted by risk')
    p.add_argument('dir')
    p.add_argument('--min-score', type=int, default=0)
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser('watch', help='check the known payload slots')
    p.add_argument('--known', default=None)
    p.set_defaults(func=cmd_watch)

    args = ap.parse_args(argv)
    try:
        return args.func(args) or 0
    except FileNotFoundError as ex:
        print('error: file not found: %s' % ex.filename, file=sys.stderr)
        return 2
    except IsADirectoryError as ex:
        print('error: %s is a folder, not a file' % ex.filename, file=sys.stderr)
        return 2
    except PermissionError as ex:
        print('error: cannot read %s' % ex.filename, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
