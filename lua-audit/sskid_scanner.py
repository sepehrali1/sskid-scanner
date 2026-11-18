#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sskid Script Scanner — اسکنر استاتیک اسکریپت‌های Lua/Luau
==========================================================
پوستهٔ گرافیکی روی موتور lua_audit.py.

هیچ فایلی اجرا نمی‌شود. فقط بایت‌ها خوانده می‌شوند.

اجرا:
    python -X utf8 sskid_scanner.py                 پنجرهٔ گرافیکی
    python -X utf8 sskid_scanner.py --no-splash     بدون صفحهٔ لودینگ
    python -X utf8 sskid_scanner.py --report <f|d> <out.txt>
"""

import contextlib
import io
import os
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

try:
    import lua_audit as la
except Exception as ex:  # pragma: no cover
    print('cannot import lua_audit.py:', ex)
    raise

APP_NAME = 'Sskid Script Scanner'
APP_TAG = 'اسکنر استاتیک اسکریپت  •  هیچ فایلی اجرا نمی‌شود'

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    HERE = getattr(sys, '_MEIPASS', HERE)
ASSETS = os.path.join(HERE, 'assets')

# ---------------------------------------------------------------- تم
# پالت از روی رنگ‌های خود عکس کاربر ساخته شده (make_assets.py):
# عکس عمدتاً مشکی است (#000000 ۸۷٪) با قرمز تیره (#aa0505) و سبز خاکستری.
THEME = {
    'bg':      '#07070b',
    'panel':   '#120e11',
    'panel2':  '#1a1418',
    'panel3':  '#251a1f',
    'line':    '#33232a',
    'fg':      '#f0eaeb',
    'dim':     '#9d8b90',
    'dim2':    '#6e5a61',
    'accent':  '#e11d2e',
    'accent2': '#ff7a45',
    'ok':      '#3ddc97',
    'warn':    '#f5b301',
    'bad':     '#ff5c7a',
    'console': '#050507',
}


# ---------------------------------------------------------------- کمک‌ها
def pick_font(candidates, size, weight='normal'):
    fams = set(tkfont.families())
    for c in candidates:
        if c in fams:
            return (c, size, weight)
    return ('Segoe UI', size, weight)


def setup_style():
    """نوارهای پیمایش تیره هم‌رنگ تم."""
    st = ttk.Style()
    try:
        st.theme_use('clam')
    except Exception:
        pass
    for orient, name in (('vertical', 'Sskid.Vertical.TScrollbar'),
                         ('horizontal', 'Sskid.Horizontal.TScrollbar')):
        st.configure(name, background=THEME['panel3'], troughcolor=THEME['console'],
                     bordercolor=THEME['line'], darkcolor=THEME['panel3'],
                     lightcolor=THEME['panel3'], arrowcolor=THEME['dim'],
                     gripcount=0, relief='flat', arrowsize=13)
        st.map(name, background=[('active', THEME['accent']),
                                 ('pressed', THEME['accent2'])],
               arrowcolor=[('active', THEME['fg'])])


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """مستطیل با گوشه‌های گرد روی Canvas."""
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def blend(c1, c2, t):
    """درهم‌آمیزی دو رنگ هگز."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def load_image(name):
    path = os.path.join(ASSETS, name)
    if os.path.exists(path):
        try:
            return tk.PhotoImage(file=path)
        except Exception:
            return None
    return None


# ---------------------------------------------------------------- ویجت‌ها
class RoundButton(tk.Canvas):
    """دکمهٔ گرد با حالت hover و فعال/غیرفعال."""

    def __init__(self, parent, text, command, width=180, height=38, radius=10,
                 fill=None, hover=None, fg=None, accent=False, anchor_text='center',
                 icon=''):
        super().__init__(parent, width=width, height=height, bg=parent['bg'],
                         highlightthickness=0, bd=0, cursor='hand2')
        self.command = command
        self.w, self.h, self.r = width, height, radius
        self.accent = accent
        self.enabled = True
        self.text = ('%s  %s' % (icon, text)) if icon else text
        self.anchor_text = anchor_text
        if accent:
            self.fill = fill or THEME['accent']
            self.hover = hover or blend(THEME['accent'], '#ffffff', .18)
            self.fg = fg or '#ffffff'
        else:
            self.fill = fill or THEME['panel3']
            self.hover = hover or blend(THEME['panel3'], '#ffffff', .10)
            self.fg = fg or THEME['fg']
        self._shape = None
        self._label = None
        self._draw()
        self.bind('<Enter>', lambda e: self._paint(self.hover))
        self.bind('<Leave>', lambda e: self._paint(self.fill))
        self.bind('<Button-1>', self._press)
        self.bind('<ButtonRelease-1>', self._release)

    def _draw(self):
        self.delete('all')
        self._shape = round_rect(self, 1, 1, self.w - 1, self.h - 1, self.r,
                                 fill=self.fill, outline='')
        x = self.w / 2 if self.anchor_text == 'center' else 14
        anchor = 'center' if self.anchor_text == 'center' else 'w'
        self._label = self.create_text(x, self.h / 2, text=self.text, fill=self.fg,
                                       font=UI_B, anchor=anchor)

    def _paint(self, color):
        if not self.enabled:
            return
        self.itemconfigure(self._shape, fill=color)

    def _press(self, _):
        if self.enabled:
            self._paint(blend(self.fill, '#000000', .25))

    def _release(self, _):
        if not self.enabled:
            return
        self._paint(self.hover)
        if callable(self.command):
            self.command()

    def set_enabled(self, on):
        self.enabled = bool(on)
        self.configure(cursor='hand2' if on else 'arrow')
        self.itemconfigure(self._shape, fill=self.fill if on else THEME['panel2'])
        self.itemconfigure(self._label, fill=self.fg if on else THEME['dim2'])

    def set_active(self, on):
        self.itemconfigure(self._shape,
                           fill=self.fill if on else THEME['panel2'],
                           outline=THEME['accent'] if on else '')
        self.itemconfigure(self._label, fill=self.fg if on else THEME['dim'])


class ScoreRing(tk.Canvas):
    """حلقهٔ امتیاز با عدد در مرکز."""

    def __init__(self, parent, size=132):
        super().__init__(parent, width=size, height=size, bg=parent['bg'],
                         highlightthickness=0, bd=0)
        self.size = size
        self.arc = None
        self.val = None
        self.sub = None
        self._draw(0, THEME['dim'])

    def _draw(self, score, color):
        self.delete('all')
        pad = 12
        w = self.size
        self.create_oval(pad, pad, w - pad, w - pad, outline=THEME['panel3'], width=11)
        extent = -359.99 * (score / 100.0) if score > 0 else -0.001
        self.create_arc(pad, pad, w - pad, w - pad, start=90, extent=extent,
                        outline=color, width=11, style='arc')
        self.val = self.create_text(w / 2, w / 2 - 6, text=str(int(score)),
                                    fill=color, font=SCORE_FONT)
        self.sub = self.create_text(w / 2, w / 2 + 26, text='/ 100',
                                    fill=THEME['dim'], font=UI)

    def set(self, score, color):
        self._draw(score, color)


class Meter(tk.Canvas):
    """نوار افقی برای تهدید/قابلیت."""

    def __init__(self, parent, width=260, height=10):
        super().__init__(parent, width=width, height=height, bg=parent['bg'],
                         highlightthickness=0, bd=0)
        self.w, self.h = width, height
        self._draw(0, THEME['ok'])

    def _draw(self, frac, color):
        self.delete('all')
        round_rect(self, 0, 0, self.w, self.h, self.h / 2, fill=THEME['panel3'], outline='')
        fw = max(0, min(1.0, frac)) * self.w
        if fw > 2:
            round_rect(self, 0, 0, fw, self.h, self.h / 2, fill=color, outline='')

    def set(self, frac, color):
        self._draw(frac, color)


class Card(tk.Frame):
    def __init__(self, parent, pad=14):
        super().__init__(parent, bg=THEME['panel'], highlightthickness=1,
                         highlightbackground=THEME['line'])
        self.body = tk.Frame(self, bg=THEME['panel'])
        self.body.pack(fill='both', expand=True, padx=pad, pady=pad)


# ---------------------------------------------------------------- اسپلش
class Splash:
    """صفحهٔ لودینگ: عکس کاربر + نام برنامه + نوار پیشرفت."""

    def __init__(self, root, on_done):
        self.root = root
        self.on_done = on_done
        self.done = False
        self.p = 0.0

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg=THEME['accent'])
        self.win.attributes('-topmost', True)

        W, H = 640, 430
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry('%dx%d+%d+%d' % (W, H, (sw - W) // 2, (sh - H) // 2))

        inner = tk.Frame(self.win, bg=THEME['bg'])
        inner.pack(fill='both', expand=True, padx=1, pady=1)

        # تصویر
        self.photo = load_image('splash.png')
        img_h = 0
        if self.photo:
            img_h = self.photo.height()
            tk.Label(inner, image=self.photo, bg=THEME['bg'], bd=0).pack(pady=(22, 0))
        else:
            tk.Label(inner, text='⌬', bg=THEME['bg'], fg=THEME['accent'],
                     font=(UI[0], 54)).pack(pady=(30, 0))

        tk.Label(inner, text=APP_NAME, bg=THEME['bg'], fg=THEME['fg'],
                 font=SPLASH_FONT).pack(pady=(16, 2))
        tk.Label(inner, text=APP_TAG, bg=THEME['bg'], fg=THEME['dim'],
                 font=UI).pack()

        self.bar = tk.Canvas(inner, width=420, height=8, bg=THEME['bg'],
                             highlightthickness=0, bd=0)
        self.bar.pack(pady=(26, 8))
        self.bar_bg = round_rect(self.bar, 0, 0, 420, 8, 4, fill=THEME['panel3'], outline='')
        self.bar_fg = None

        self.status = tk.Label(inner, text='در حال آماده‌سازی…', bg=THEME['bg'],
                               fg=THEME['dim'], font=UI)
        self.status.pack()

        self.win.attributes('-alpha', 0.0)
        self._fade(0.0)
        self.win.bind('<Button-1>', lambda e: self.finish())
        self.win.bind('<Escape>', lambda e: self.finish())
        self.win.focus_force()
        self.win.after(30, self._tick)

    def _fade(self, a):
        try:
            self.win.attributes('-alpha', a)
        except Exception:
            pass

    def _tick(self):
        if self.done:
            return
        self.p = min(100.0, self.p + 3.2)
        a = min(1.0, self.p / 12.0)
        self._fade(a)
        w = int(420 * self.p / 100.0)
        self.bar.delete(self.bar_fg) if self.bar_fg else None
        self.bar_fg = round_rect(self.bar, 0, 0, max(1, w), 8, 4,
                                 fill=blend(THEME['accent'], THEME['accent2'],
                                            self.p / 100.0), outline='')
        msg = 'بارگذاری موتور…'
        if self.p > 40:
            msg = 'آماده‌سازی رابط کاربری…'
        if self.p > 75:
            msg = 'بررسی فایل‌های داخلی…'
        if self.p > 92:
            msg = 'آماده است'
        self.status.configure(text=msg)
        if self.p >= 100:
            self.win.after(160, self.finish)
        else:
            self.win.after(24, self._tick)

    def finish(self):
        if self.done:
            return
        self.done = True
        self._fade(0.0)
        self.win.after(120, self._close)

    def _close(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        self.on_done()


# ---------------------------------------------------------------- برنامه
class Scanner:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.busy = False
        self.mode = 'scan'
        self.nav = {}
        self._build()
        self.root.after(80, self._pump)
        self.select('scan')

    # ------------------------------------------------------------ چیدمان
    def _build(self):
        r = self.root
        setup_style()
        r.title(APP_NAME)
        r.configure(bg=THEME['bg'])
        r.geometry('1180x800')
        r.minsize(980, 640)

        ico = os.path.join(ASSETS, 'icon.ico')
        if os.path.exists(ico):
            try:
                r.iconbitmap(ico)
            except Exception:
                pass
        self.logo_img = load_image('logo.png')

        self._header()

        body = tk.Frame(r, bg=THEME['bg'])
        body.pack(fill='both', expand=True, padx=14, pady=(0, 10))

        self._sidebar(body)

        main = tk.Frame(body, bg=THEME['bg'])
        main.pack(side='left', fill='both', expand=True, padx=(14, 0))

        self._target_card(main)
        self._options_card(main)
        self._verdict_card(main)
        self._console(main)
        self._statusbar(main)

        r.bind('<Control-o>', lambda e: self.pick_file())
        r.bind('<Control-Return>', lambda e: self.run(self.mode))
        r.bind('<F5>', lambda e: self.run(self.mode))
        r.bind('<Escape>', lambda e: self.root.destroy())

    # ---------- سربرگ گرادیانی
    def _header(self):
        self.head = tk.Canvas(self.root, height=86, bg=THEME['bg'],
                              highlightthickness=0, bd=0)
        self.head.pack(fill='x')
        self.head.bind('<Configure>', lambda e: self._paint_header(e.width))

    def _paint_header(self, w):
        c = self.head
        c.delete('all')
        c.create_rectangle(0, 0, w, 86, fill=THEME['panel'], outline='')
        for i in range(w):
            t = i / max(1, w)
            c.create_line(i, 0, i, 86, fill=blend(THEME['panel'], THEME['accent'], 0.10 * (1 - t)))
        c.create_line(0, 85, w, 85, fill=THEME['line'])
        # نوار لهجه‌دار سمت چپ
        c.create_rectangle(0, 0, 4, 86, fill=THEME['accent'], outline='')
        if self.logo_img:
            c.create_image(30, 43, image=self.logo_img, anchor='w')
            tx = 30 + self.logo_img.width() + 16
        else:
            c.create_text(30, 43, text='⌬', fill=THEME['accent'],
                          font=(UI[0], 30), anchor='w')
            tx = 60
        c.create_text(tx, 32, text=APP_NAME, fill=THEME['fg'], font=HEAD_FONT, anchor='w')
        c.create_text(tx, 57, text=APP_TAG, fill=THEME['dim'], font=UI, anchor='w')
        # نشانگر مشغول بودن
        self.busy_dot = c.create_text(w - 30, 43, text='', fill=THEME['accent2'],
                                      font=UI_B, anchor='e')

    def _busy_text(self, text):
        if getattr(self, 'busy_dot', None):
            self.head.itemconfigure(self.busy_dot, text=text)

    # ---------- سایدبار
    def _sidebar(self, parent):
        side = tk.Frame(parent, bg=THEME['panel'], width=224,
                        highlightthickness=1, highlightbackground=THEME['line'])
        side.pack(side='left', fill='y')
        side.pack_propagate(False)

        tk.Label(side, text='ابزارها', bg=THEME['panel'], fg=THEME['dim2'],
                 font=(UI[0], 9, 'bold')).pack(anchor='w', padx=16, pady=(14, 6))

        items = [
            ('scan',    '🔎', 'بازرسی کامل',      'امتیاز، حکم، یافته‌ها و URLها'),
            ('hash',    '#️⃣', 'هش و آنتروپی',    'md5 / sha1 / sha256 + آنتروپی'),
            ('urls',    '🌐', 'استخراج URL',      'همهٔ آدرس‌های یک فایل یا پوشه'),
            ('strings', '🔤', 'رشته‌ها',          'بیرون کشیدن متن‌ها + دیکد escape'),
            ('batch',   '📁', 'اسکن پوشه',        'همهٔ فایل‌ها، مرتب بر اساس ریسک'),
            ('watch',   '📡', 'اسلات‌های آنلاین',  'چک کردن دو اسلات شناخته‌شده'),
        ]
        self.desc = {}
        for key, icon, title, desc in items:
            b = RoundButton(side, title, lambda k=key: self.select(k), width=192,
                            height=42, icon=icon, anchor_text='left')
            b.pack(padx=14, pady=3)
            self.nav[key] = b
            self.desc[key] = desc

        tk.Frame(side, bg=THEME['line'], height=1).pack(fill='x', padx=14, pady=(12, 10))

        self.tip = tk.Label(side, text='', bg=THEME['panel'], fg=THEME['dim'],
                            font=(UI[0], 9), wraplength=190, justify='right')
        self.tip.pack(anchor='w', padx=16)

        tk.Label(side, text='v2  •  بدون اجرای فایل هدف', bg=THEME['panel'],
                 fg=THEME['dim2'], font=(UI[0], 8)).pack(side='bottom', pady=(0, 4))
        self.run_btn = RoundButton(side, 'اجرا  (F5)', lambda: self.run(self.mode),
                                   width=192, height=44, accent=True, icon='▶')
        self.run_btn.pack(side='bottom', padx=14, pady=(0, 12))

    # ---------- کارت هدف
    def _target_card(self, parent):
        card = Card(parent, pad=12)
        card.pack(fill='x', pady=(0, 10))
        b = card.body

        tk.Label(b, text='هدف', bg=THEME['panel'], fg=THEME['dim2'],
                 font=(UI[0], 9, 'bold')).pack(anchor='w')
        row = tk.Frame(b, bg=THEME['panel'])
        row.pack(fill='x', pady=(6, 0))

        wrap = tk.Frame(row, bg=THEME['panel2'], highlightthickness=1,
                        highlightbackground=THEME['line'])
        wrap.pack(side='left', fill='x', expand=True)
        self.path_var = tk.StringVar()
        self.entry = tk.Entry(wrap, textvariable=self.path_var, bg=THEME['panel2'],
                              fg=THEME['fg'], font=UI, relief='flat',
                              insertbackground=THEME['accent'], highlightthickness=0)
        self.entry.pack(fill='x', padx=10, pady=7)
        self.entry.bind('<Return>', lambda e: self.run(self.mode))

        RoundButton(row, 'فایل', self.pick_file, width=84, height=34,
                    icon='📄').pack(side='left', padx=(8, 0))
        RoundButton(row, 'پوشه', self.pick_dir, width=84, height=34,
                    icon='📂').pack(side='left', padx=(6, 0))

    # ---------- کارت گزینه‌ها
    def _options_card(self, parent):
        card = Card(parent, pad=12)
        card.pack(fill='x', pady=(0, 10))
        b = card.body
        row = tk.Frame(b, bg=THEME['panel'])
        row.pack(fill='x')

        self.min_score = tk.IntVar(value=25)
        self.min_str = tk.IntVar(value=6)
        self.grep_var = tk.StringVar()

        def field(label, var, width=5, from_=0, to=100):
            f = tk.Frame(row, bg=THEME['panel'])
            f.pack(side='left', padx=(0, 22))
            tk.Label(f, text=label, bg=THEME['panel'], fg=THEME['dim2'],
                     font=(UI[0], 9, 'bold')).pack(anchor='w')
            box = tk.Frame(f, bg=THEME['panel2'], highlightthickness=1,
                           highlightbackground=THEME['line'])
            box.pack(anchor='w', pady=(5, 0))
            tk.Spinbox(box, from_=from_, to=to, textvariable=var, width=width,
                       bg=THEME['panel2'], fg=THEME['fg'], font=UI, relief='flat',
                       buttonbackground=THEME['panel3'], highlightthickness=0,
                       insertbackground=THEME['fg'], justify='center').pack(padx=2, pady=2)

        field('حداقل امتیاز', self.min_score)
        field('حداقل طول رشته', self.min_str, from_=2, to=40)

        f = tk.Frame(row, bg=THEME['panel'])
        f.pack(side='left', fill='x', expand=True)
        tk.Label(f, text='فیلتر رشته‌ها', bg=THEME['panel'], fg=THEME['dim2'],
                 font=(UI[0], 9, 'bold')).pack(anchor='w')
        box = tk.Frame(f, bg=THEME['panel2'], highlightthickness=1,
                       highlightbackground=THEME['line'])
        box.pack(fill='x', pady=(5, 0))
        tk.Entry(box, textvariable=self.grep_var, bg=THEME['panel2'], fg=THEME['fg'],
                 font=UI, relief='flat', insertbackground=THEME['accent'],
                 highlightthickness=0).pack(fill='x', padx=8, pady=5)

    # ---------- کارت حکم
    def _verdict_card(self, parent):
        self.vcard = Card(parent, pad=14)
        b = self.vcard.body

        left = tk.Frame(b, bg=THEME['panel'])
        left.pack(side='left')
        self.ring = ScoreRing(left, 132)
        self.ring.pack()

        mid = tk.Frame(b, bg=THEME['panel'])
        mid.pack(side='left', fill='both', expand=True, padx=(18, 0))

        self.v_label = tk.Label(mid, text='—', bg=THEME['panel'], fg=THEME['dim'],
                                font=VERDICT_FONT)
        self.v_label.pack(anchor='w')
        self.v_note = tk.Label(mid, text='', bg=THEME['panel'], fg=THEME['dim'],
                               font=UI, justify='right', wraplength=430)
        self.v_note.pack(anchor='w', pady=(4, 10))

        self.threat_lbl = tk.Label(mid, text='تهدید 0', bg=THEME['panel'],
                                   fg=THEME['dim'], font=(UI[0], 9, 'bold'))
        self.threat_lbl.pack(anchor='w')
        self.threat_meter = Meter(mid, width=330)
        self.threat_meter.pack(anchor='w', pady=(2, 8))

        self.cap_lbl = tk.Label(mid, text='قابلیت 0', bg=THEME['panel'],
                                fg=THEME['dim'], font=(UI[0], 9, 'bold'))
        self.cap_lbl.pack(anchor='w')
        self.cap_meter = Meter(mid, width=330)
        self.cap_meter.pack(anchor='w', pady=(2, 0))

        self.v_meta = tk.Label(b, text='', bg=THEME['panel'], fg=THEME['dim2'],
                               font=(UI[0], 9), justify='left')
        self.v_meta.pack(side='right', anchor='n')
        self.vcard.pack_forget()

    # ---------- کنسول
    def _console(self, parent):
        wrap = tk.Frame(parent, bg=THEME['panel'], highlightthickness=1,
                        highlightbackground=THEME['line'])
        wrap.pack(fill='both', expand=True)

        bar = tk.Frame(wrap, bg=THEME['panel'])
        bar.pack(fill='x')
        tk.Label(bar, text='  خروجی', bg=THEME['panel'], fg=THEME['dim2'],
                 font=(UI[0], 9, 'bold')).pack(side='left', pady=6)
        RoundButton(bar, 'ذخیره', self.save_report, width=78, height=28,
                    icon='💾').pack(side='right', padx=(6, 10), pady=4)
        RoundButton(bar, 'کپی', self.copy_report, width=70, height=28,
                    icon='📋').pack(side='right', padx=0, pady=4)
        RoundButton(bar, 'پاک', self.clear, width=64, height=28,
                    icon='✕').pack(side='right', padx=6, pady=4)

        box = tk.Frame(wrap, bg=THEME['console'])
        box.pack(fill='both', expand=True, padx=1, pady=(0, 1))
        self.txt = tk.Text(box, bg=THEME['console'], fg='#c6c9dd', font=MONO,
                           relief='flat', wrap='none', insertbackground=THEME['accent'],
                           padx=14, pady=10, selectbackground='#33254d',
                           highlightthickness=0, bd=0)
        vs = ttk.Scrollbar(box, orient='vertical', command=self.txt.yview,
                           style='Sskid.Vertical.TScrollbar')
        hs = ttk.Scrollbar(box, orient='horizontal', command=self.txt.xview,
                           style='Sskid.Horizontal.TScrollbar')
        self.txt.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side='right', fill='y')
        hs.pack(side='bottom', fill='x')
        self.txt.pack(fill='both', expand=True)

        self.txt.tag_configure('threat', foreground=THEME['bad'])
        self.txt.tag_configure('can', foreground=THEME['warn'])
        self.txt.tag_configure('ok', foreground=THEME['ok'])
        self.txt.tag_configure('head', foreground=THEME['accent'], font=MONO_B)
        self.txt.tag_configure('dim', foreground=THEME['dim2'])
        self.txt.tag_configure('url', foreground=THEME['accent2'])
        self.txt.insert('end', self.welcome(), 'dim')

    def _statusbar(self, parent):
        bar = tk.Frame(parent, bg=THEME['bg'])
        bar.pack(fill='x', pady=(8, 0))
        self.status_lbl = tk.Label(bar, text='آماده', bg=THEME['bg'],
                                   fg=THEME['dim'], font=UI_B)
        self.status_lbl.pack(side='left')
        self.status_extra = tk.Label(bar, text='', bg=THEME['bg'],
                                     fg=THEME['dim2'], font=UI)
        self.status_extra.pack(side='right')

    def welcome(self):
        return (
            '\n'
            '   ⌬  %s\n\n'
            '   ۱) یک فایل Lua/Luau انتخاب کن (Ctrl+O)\n'
            '   ۲) از سایدبار یک ابزار بردار و «اجرا» را بزن (F5)\n'
            '   ۳) اگر فایل بسته‌بندی‌شده باشد، برنامه صریح می‌گوید «داخلش دیده نشد»\n\n'
            '   هیچ فایلی اجرا نمی‌شود — فقط بایت‌ها خوانده می‌شوند.\n' % APP_NAME
        )

    # ------------------------------------------------------------ انتخاب ابزار
    def select(self, key):
        self.mode = key
        for k, b in self.nav.items():
            b.set_active(k == key)
        self.tip.configure(text=self.desc[key])
        self.status_extra.configure(text='ابزار فعال: %s' % self.desc[key])

    # ------------------------------------------------------------ فایل
    def pick_file(self):
        p = filedialog.askopenfilename(
            title='انتخاب فایل اسکریپت',
            filetypes=[('Lua / Luau', '*.lua *.luau'), ('همهٔ فایل‌ها', '*.*')])
        if p:
            self.path_var.set(p)

    def pick_dir(self):
        p = filedialog.askdirectory(title='انتخاب پوشه')
        if p:
            self.path_var.set(p)

    # ------------------------------------------------------------ اجرا
    def run(self, mode=None):
        if self.busy:
            return
        mode = mode or self.mode
        path = self.path_var.get().strip().strip('"')

        if mode != 'watch':
            if not path:
                messagebox.showinfo('انتخاب نشده', 'اول یک فایل یا پوشه انتخاب کن.')
                return
            if not os.path.exists(path):
                messagebox.showerror('پیدا نشد', 'این مسیر وجود ندارد:\n%s' % path)
                return
            if mode == 'batch' and not os.path.isdir(path):
                messagebox.showerror('پوشه لازم است', '«اسکن پوشه» یک پوشه می‌خواهد.')
                return
            if mode in ('scan', 'hash', 'strings') and os.path.isdir(path):
                messagebox.showerror('فایل لازم است', 'این ابزار یک فایل می‌خواهد، نه پوشه.')
                return

        opts = {'min_score': self.min_score.get(), 'min_str': self.min_str.get(),
                'grep': self.grep_var.get().strip() or None}

        self.busy = True
        self.run_btn.set_enabled(False)
        self._busy_text('⏳ در حال بررسی…')
        self.set_status('در حال کار…', THEME['accent2'])
        self.txt.delete('1.0', 'end')
        self.txt.insert('end', 'بررسی %s …\n\n' % (path or 'اسلات‌های آنلاین'), 'dim')

        threading.Thread(target=self._work, args=(mode, path, opts), daemon=True).start()

    def _work(self, mode, path, opts):
        try:
            if mode == 'scan':
                r = la.scan_file(path)
                self.q.put(('scan', la.render_scan(r), r))
            elif mode == 'batch':
                buf = io.StringIO()
                ns = type('N', (), {'dir': path, 'min_score': opts['min_score']})()
                with contextlib.redirect_stdout(buf):
                    la.cmd_batch(ns)
                self.q.put(('text', buf.getvalue(), None))
            else:
                buf = io.StringIO()
                if mode == 'hash':
                    fn, ns = la.cmd_hash, type('N', (), {'file': path})()
                elif mode == 'urls':
                    fn, ns = la.cmd_urls, type('N', (), {'target': path})()
                elif mode == 'strings':
                    fn, ns = la.cmd_strings, type('N', (), {
                        'target': path, 'min': opts['min_str'], 'grep': opts['grep'],
                        'escapes': True, 'limit': 3000, 'width': 240})()
                else:
                    fn, ns = la.cmd_watch, type('N', (), {'known': None})()
                with contextlib.redirect_stdout(buf):
                    fn(ns)
                self.q.put(('text', buf.getvalue(), None))
        except Exception:
            self.q.put(('error', traceback.format_exc(), None))

    def _pump(self):
        try:
            while True:
                kind, text, extra = self.q.get_nowait()
                if kind == 'error':
                    self.txt.delete('1.0', 'end')
                    self.txt.insert('end', text, 'threat')
                    self.set_status('خطا', THEME['bad'])
                else:
                    self.txt.delete('1.0', 'end')
                    self._render(text)
                    if kind == 'scan' and extra:
                        self._verdict(extra)
                    else:
                        self.vcard.pack_forget()
                        self.set_status('تمام', THEME['ok'])
                self.busy = False
                self.run_btn.set_enabled(True)
                self._busy_text('')
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    def _render(self, text):
        for line in text.split('\n'):
            tag = None
            if line.startswith('  [THREAT]'):
                tag = 'threat'
            elif line.startswith('  [can'):
                tag = 'can'
            elif line.startswith('VERDICT'):
                tag = 'head'
            elif line.startswith('  http') or line.startswith('  discord'):
                tag = 'url'
            elif line.startswith('=====') or line.startswith('NOTE') or line.startswith('  '):
                tag = 'dim'
            self.txt.insert('end', line + '\n', tag)

    def _verdict(self, r):
        v = r['verdict']
        color = {'DO NOT RUN': THEME['bad'], 'REVIEW': THEME['warn'],
                 'LOW RISK': THEME['ok']}.get(v, THEME['dim'])
        self.ring.set(r['score'], color)
        self.v_label.configure(text=v, fg=color)
        if not r.get('auditable', True):
            note = ('فایل بسته‌بندی‌شده است؛ داخلش خوانده نشد. '
                    '«یافته‌ای نبود» یعنی «نتوانستم ببینم»، نه «امن است».')
        elif v == 'DO NOT RUN':
            note = 'کد از راه دور می‌آید/می‌رود یا خودش را پنهان می‌کند. اجرا نکن.'
        elif v == 'REVIEW':
            note = 'یا ناشناخته است یا قابلیت زیادی دارد. خودت بخوان.'
        else:
            note = 'نشانهٔ مشکوکی پیدا نشد.'
        self.v_note.configure(text=note)

        th, cap = r.get('threat', 0), r.get('capability', 0)
        self.threat_lbl.configure(text='تهدید  %d' % th)
        self.threat_meter.set(min(1.0, th / 100.0), THEME['bad'] if th >= 50 else
                              (THEME['warn'] if th >= 20 else THEME['ok']))
        self.cap_lbl.configure(text='قابلیت  %d' % cap)
        self.cap_meter.set(min(1.0, cap / 100.0), THEME['accent2'])

        obf = ', '.join(r.get('obfuscators') or []) or '—'
        self.v_meta.configure(text='حجم: %s بایت\nآنتروپی: %.2f\nبسته‌بندی: %s\nURL: %d   وب‌هوک: %d'
                                   % (f"{r['bytes']:,}", r['entropy'], obf,
                                      len(r['urls']), r['webhook_count']))
        if not self.vcard.winfo_ismapped():
            self.vcard.pack(fill='x', pady=(0, 10), before=self.txt.master.master)
        self.set_status(v, color)
        self.status_extra.configure(text='امتیاز %d/100' % r['score'])

    def set_status(self, text, color=THEME['dim']):
        self.status_lbl.configure(text=text, fg=color)

    # ------------------------------------------------------------ خروجی
    def clear(self):
        self.txt.delete('1.0', 'end')
        self.vcard.pack_forget()
        self.set_status('آماده', THEME['dim'])
        self.status_extra.configure(text='')

    def copy_report(self):
        data = self.txt.get('1.0', 'end').strip()
        if not data:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self.set_status('در کلیپ‌بورد کپی شد', THEME['ok'])

    def save_report(self):
        data = self.txt.get('1.0', 'end').strip()
        if not data:
            messagebox.showinfo('خالی', 'چیزی برای ذخیره نیست.')
            return
        p = filedialog.asksaveasfilename(title='ذخیرهٔ گزارش', defaultextension='.txt',
                                         filetypes=[('متن', '*.txt'), ('همهٔ فایل‌ها', '*.*')])
        if not p:
            return
        with open(p, 'w', encoding='utf-8') as f:
            f.write(data + '\n')
        self.set_status('ذخیره شد: %s' % os.path.basename(p), THEME['ok'])


# ---------------------------------------------------------------- ورود
def crash_log(exc_text):
    try:
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        if not os.access(base, os.W_OK):
            base = os.path.join(os.environ.get('LOCALAPPDATA', base), APP_NAME)
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, 'crash.log'), 'a', encoding='utf-8') as f:
            f.write('\n--- %s ---\n%s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), exc_text))
    except Exception:
        pass


def headless(argv):
    """SskidScriptScanner.exe --report <file|dir> <out.txt>"""
    try:
        target, out = argv[0], (argv[1] if len(argv) > 1 else 'sskid-report.txt')
        buf = io.StringIO()
        if os.path.isdir(target):
            ns = type('N', (), {'dir': target, 'min_score': 0})()
            with contextlib.redirect_stdout(buf):
                la.cmd_batch(ns)
        else:
            with contextlib.redirect_stdout(buf):
                print(la.render_scan(la.scan_file(target)))
        with open(out, 'w', encoding='utf-8') as f:
            f.write(buf.getvalue())
        return 0
    except Exception:
        crash_log(traceback.format_exc())
        return 2


def main():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    argv = sys.argv[1:]
    if argv and argv[0] in ('--report', '-r'):
        sys.exit(headless(argv[1:]))
    show_splash = '--no-splash' not in argv

    global UI, UI_B, MONO, MONO_B, HEAD_FONT, TITLE_FONT, VERDICT_FONT, SPLASH_FONT, SCORE_FONT

    try:
        root = tk.Tk()
        root.withdraw()
        UI = pick_font(['Segoe UI Variable Text', 'Segoe UI', 'Tahoma'], 10)
        UI_B = pick_font(['Segoe UI Variable Text', 'Segoe UI', 'Tahoma'], 10, 'bold')
        MONO = pick_font(['Cascadia Mono', 'Consolas', 'Courier New'], 10)
        MONO_B = pick_font(['Cascadia Mono', 'Consolas', 'Courier New'], 10, 'bold')
        HEAD_FONT = pick_font(['Segoe UI Variable Display', 'Segoe UI'], 17, 'bold')
        TITLE_FONT = pick_font(['Segoe UI Variable Display', 'Segoe UI'], 22, 'bold')
        VERDICT_FONT = pick_font(['Segoe UI Variable Display', 'Segoe UI'], 26, 'bold')
        SPLASH_FONT = pick_font(['Segoe UI Variable Display', 'Segoe UI'], 20, 'bold')
        SCORE_FONT = pick_font(['Segoe UI Variable Display', 'Segoe UI'], 26, 'bold')

        app_holder = {}

        def start_app():
            root.deiconify()
            app_holder['app'] = Scanner(root)

        if show_splash:
            Splash(root, start_app)
        else:
            start_app()

        root.mainloop()
    except Exception:
        crash_log(traceback.format_exc())
        raise


# مقادیر پیش‌فرض تا وقتی main آن‌ها را می‌سازد
UI = ('Segoe UI', 10)
UI_B = ('Segoe UI', 10, 'bold')
MONO = ('Consolas', 10)
MONO_B = ('Consolas', 10, 'bold')
HEAD_FONT = ('Segoe UI', 17, 'bold')
TITLE_FONT = ('Segoe UI', 22, 'bold')
VERDICT_FONT = ('Segoe UI', 26, 'bold')
SPLASH_FONT = ('Segoe UI', 20, 'bold')
SCORE_FONT = ('Segoe UI', 26, 'bold')


if __name__ == '__main__':
    main()
