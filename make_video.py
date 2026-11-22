"""Демо-видео механики «Скорлупа» (BigBalls) -> out/shell_demo.mp4
1080x1920, 30 fps, 30 с, H.264 + AAC. Кадры рисуются Pillow и идут потоком в FFmpeg (PNG не сохраняются).
Запуск:  python make_video.py
"""
import hashlib, math, os, random, secrets, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'out')
W, H, FPS, DUR = 1080, 1920, 30, 30.0
NF = int(DUR * FPS)
SR = 48000

NAVY, ORANGE, GREEN, GOLD, WHITE = (21, 28, 44), (240, 116, 42), (46, 125, 90), (232, 179, 58), (255, 255, 255)
MINT = (127, 224, 176)
PRIZE = 'Скин-заглушка'
PLAYERS = ['Котик228', 'Охотник', 'Няша_77', 'Гром', 'Лиса', 'Бублик', 'Вихрь_9', 'Луна', 'Орешек', 'Жар-птица', 'Кирпич', 'Сова']

# ---- таймлайн (с) ----
T_SEAL, T_HASH0, T_HASH1 = .8, 1.1, 2.2   # плашка «Приз запечатан» + короткий хэш
T_RUN, T_BREAK = 3.0, 18.0       # отсчёт 15 с
T_02, T_03 = 8.0, 13.0
T_05 = 18.9
T_PRIZE, T_WIN, T_BADGE = 19.6, 20.8, 21.6        # приз, победитель, значок «✓ Честно»
T_TAP, T_OPEN = 22.8, 23.0                        # тап по значку -> окно проверки
T_KEY0, T_KEY1, T_HR1, T_CHECK, T_FORM = 23.5, 24.0, 24.9, 25.2, 25.9
T_TAP2, T_CLOSE, T_AGAIN = 27.9, 28.1, 28.4      # «Закрыть», «Повторить»
JOIN = 6.0                       # зритель жмёт «Греть» = участвует (один раз)
TAPS = [JOIN]

# ---- проверка ассетов ----
assets = {}
missing = []
for i in range(1, 7):
    cands = [f for f in os.listdir(os.path.join(ROOT, 'assets')) if os.path.splitext(f)[0] == f'0{i}'
             and os.path.splitext(f)[1].lower() in ('.png', '.jpg', '.jpeg', '.jfif')] if os.path.isdir(os.path.join(ROOT, 'assets')) else []
    if cands:
        assets[i] = os.path.join(ROOT, 'assets', cands[0])
    else:
        missing.append(f'0{i}')
if missing:
    sys.exit('Не хватает ассетов: ' + ', '.join(missing))


def load_stage(path):
    im = Image.open(path).convert('RGB')
    r = im.width / im.height
    if abs(r - 9 / 16) < 0.01:
        return ImageOps.fit(im, (W, H), Image.LANCZOS)
    # другие пропорции: целиком по ширине/высоте поверх размытой cover-копии
    bg = ImageOps.fit(im, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    fg = ImageOps.contain(im, (W, H), Image.LANCZOS)
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    return bg


from PIL import ImageFilter  # noqa: E402

# виньетка как в HTML (#vign)
y = np.arange(H, dtype=np.float32) / H
va = np.where(y < .2, .75 * (1 - y / .2), 0) + np.where(y > .72, .55 * (y - .72) / .28, 0)
va = va[:, None, None]
navy_arr = np.array(NAVY, np.float32)


def bake(im):
    a = np.asarray(im, np.float32)
    return Image.fromarray((a * (1 - va) + navy_arr * va).astype(np.uint8))


STAGES = {i: bake(load_stage(p)) for i, p in assets.items()}
WARM = Image.new('RGB', (W, H), (255, 246, 216))

# ---- шрифты ----
FD = r'C:\Windows\Fonts'
def F(name, size): return ImageFont.truetype(os.path.join(FD, name), size)
f_brand, f_sub, f_badge = F('seguibl.ttf', 76), F('segoeuib.ttf', 30), F('seguibl.ttf', 22)
f_timer, f_heat, f_cap = F('seguibl.ttf', 124), F('segoeuib.ttf', 44), F('segoeuib.ttf', 32)
f_lbl, f_hash, f_btn = F('segoeuib.ttf', 20), F('consola.ttf', 27), F('seguibl.ttf', 50)
f_hook, f_prize, f_mono, f_row = F('seguibl.ttf', 76), F('seguibl.ttf', 54), F('consola.ttf', 24), F('segoeuib.ttf', 28)
f_plus, f_btn2, f_hint = F('seguibl.ttf', 40), F('seguibl.ttf', 40), F('segoeuib.ttf', 26)
f_seal, f_mono_s, f_win = F('segoeuib.ttf', 30), F('consola.ttf', 22), F('seguibl.ttf', 40)
f_mtitle, f_body, f_close = F('seguibl.ttf', 40), F('segoeui.ttf', 24), F('segoeuib.ttf', 30)

# ---- криптография (настоящий SHA-256) ----
KEY = secrets.token_hex(16)
COMMIT = hashlib.sha256((PRIZE + KEY).encode('utf-8')).hexdigest()
CALC = hashlib.sha256((PRIZE + KEY).encode('utf-8')).hexdigest()   # пересчёт «при раскрытии»


# ---- утилиты ----
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def ramp(t, a, b): return clamp((t - a) / (b - a))
def ease(x): return x * x * (3 - 2 * x)
def back(x):
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def txt(d, xy, s, font, fill, a=1., stroke=8, anchor='mt', sfill=NAVY):
    if a <= 0: return
    A = int(255 * a)
    d.text(xy, s, font=font, fill=fill + (A,), anchor=anchor, stroke_width=stroke, stroke_fill=sfill + (A,))


def txt_parts(d, cx, y, parts, font, a=1., stroke=8):
    """Несколько цветных кусков одной строкой, по центру cx."""
    total = sum(font.getlength(s) for s, _ in parts)
    x = cx - total / 2
    for s, col in parts:
        txt(d, (x, y), s, font, col, a, stroke, anchor='lt')
        x += font.getlength(s)


def heaters_at(t):
    base = 57
    if t < T_RUN: return base
    tt = min(t, T_BREAK) - T_RUN
    auto = int(2 * tt + 0.22 * tt * tt)          # растёт и ускоряется
    taps = sum(1 for x in TAPS if x <= t)
    return base + auto + taps


MYNUM = heaters_at(JOIN)                       # номер зрителя в списке
N_FINAL = heaters_at(T_BREAK - 1e-6)           # список замораживается на нуле
WIN = int(KEY[:8], 16) % N_FINAL               # индекс победителя (0..N-1)
WIN_TXT = 'это ты!' if WIN + 1 == MYNUM else PLAYERS[WIN % len(PLAYERS)]


# ---- частицы (детерминированно) ----
rng = random.Random(7)
parts = []
def burst(n, x, y, sp):
    for _ in range(n):
        a = rng.random() * math.tau; v = sp * (.3 + rng.random())
        parts.append([x, y, math.cos(a) * v, math.sin(a) * v - sp * .2, 0., .8 + rng.random() * 1.4, 2 + rng.random() * 4, 300.])
def ember():
    parts.append([280 + rng.random() * 520, 1300 + rng.random() * 180, (rng.random() - .5) * 20, -40 - rng.random() * 80,
                  0., 2 + rng.random() * 2.5, 1.5 + rng.random() * 3, 0.])
BURSTS = [(T_02, 14, 700, 700, 160), (T_03, 24, 540, 950, 220), (T_BREAK, 140, 540, 990, 650), (T_PRIZE, 60, 540, 840, 300)]
BURSTS += [(x, 10, 540, 1420, 260) for x in TAPS]


def step_particles(t, dt):
    rate = .4 if t < T_03 else (1.4 if t < T_BREAK else .6)
    if rng.random() < rate: ember()
    for b in BURSTS:
        if b[0] <= t < b[0] + dt: burst(*b[1:])
    alive = []
    for p in parts:
        p[4] += dt
        if p[4] < p[5]:
            p[3] += p[7] * dt; p[0] += p[2] * dt; p[1] += p[3] * dt
            alive.append(p)
    parts[:] = alive


def draw_particles(d):
    for x, y, _, _, age, life, r, _ in parts:
        a = 1 - age / life
        R = r * 3
        d.ellipse((x - R, y - R, x + R, y + R), fill=(240, 140, 50, int(70 * a)))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 236, 180, int(235 * a)))


# ---- фон ----
def background(t):
    def pair():
        if t < .6: return 6, 6, 0
        if t < 1.4: return 6, 1, ease(ramp(t, .6, 1.4))
        if t < T_02: return 1, 1, 0
        if t < T_02 + .6: return 1, 2, ease(ramp(t, T_02, T_02 + .6))
        if t < T_03: return 2, 2, 0
        if t < T_03 + .5: return 2, 3, ease(ramp(t, T_03, T_03 + .5))
        if t < T_BREAK: return 3, 3, 0
        if t < T_05: return 4, 4, 0
        if t < T_05 + .6: return 4, 5, ease(ramp(t, T_05, T_05 + .6))
        return 5, 5, 0
    a, b, w = pair()
    im = STAGES[a] if w == 0 else Image.blend(STAGES[a], STAGES[b], w)
    # наезд
    if t < T_RUN: z = 1.
    elif t < T_BREAK: z = 1 + .04 * (t - T_RUN) / (T_BREAK - T_RUN)
    elif t < T_05: z = 1.04 + .03 * ease(ramp(t, T_BREAK, T_BREAK + .12))
    else: z = 1.07 - .07 * ease(ramp(t, T_05, T_05 + 1.6))
    dx = dy = 0.
    if T_03 <= t < T_BREAK:
        amp = 2 + 12 * (t - T_03) / (T_BREAK - T_03)
        r2 = random.Random(int(t * FPS))
        dx, dy = (r2.random() - .5) * amp, (r2.random() - .5) * amp
    if z == 1 and dx == 0 and dy == 0:
        return im.copy()
    cx, cy = 540, 990
    w_, h_ = W / z, H / z
    x0 = cx - cx / z - dx / z; y0 = cy - cy / z - dy / z
    return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w_, y0 + h_))


def button(d, t, label, col, a, press=0., joined=False):
    if a <= 0: return
    A = int(255 * a); oy = 5 * press
    if joined:   # «Ты греешь ✓ · №N» — тёмная с золотой рамкой, неактивная
        d.rounded_rectangle((280, 1440, 800, 1548), 54, fill=NAVY + (int(235 * a),), outline=GOLD + (A,), width=4)
        tw = f_btn2.getlength(label) + 46
        x0 = 540 - tw / 2
        d.line([(x0 + 4, 1494), (x0 + 15, 1506), (x0 + 34, 1480)], fill=MINT + (A,), width=7, joint='curve')
        txt(d, (x0 + 46, 1494), label, f_btn2, WHITE, a, 0, 'lm')
        return
    shadow = tuple(int(c * .5) for c in col)
    d.rounded_rectangle((300, 1448, 780, 1556), 54, fill=shadow + (A,))
    d.rounded_rectangle((300, 1440 + oy, 780, 1548 + oy), 54, fill=col + (A,), outline=NAVY + (A,), width=4)
    d.rounded_rectangle((316, 1450 + oy, 764, 1490 + oy), 30, fill=tuple(min(255, c + 40) for c in col) + (int(A * .55),))
    txt(d, (540, 1494 + oy), label, f_btn, WHITE, a, 7, 'mm')


def gem(d, s):
    if s <= 0: return
    cx, cy = 540, 840
    def P(pts): return [(cx + (x - 75) * s, cy + (y - 67) * s) for x, y in pts]
    for k in range(4, 0, -1):
        R = 120 * s * (1 + k * .18)
        d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(232, 179, 58, 22))
    d.polygon(P([(28, 8), (122, 8), (146, 44), (75, 126), (4, 44)]), fill=(214, 92, 34, 255), outline=NAVY + (255,), width=max(1, int(5 * s)))
    d.polygon(P([(28, 8), (52, 44), (75, 8)]), fill=(255, 210, 168, 255))
    d.polygon(P([(75, 8), (98, 44), (122, 8)]), fill=(255, 154, 92, 255))
    d.polygon(P([(4, 44), (146, 44), (75, 126)]), fill=(184, 70, 26, 255))
    d.line(P([(4, 44), (52, 44), (75, 126), (98, 44), (146, 44)]), fill=GOLD + (255,), width=max(1, int(3 * s)))
    d.line(P([(52, 44), (75, 8), (98, 44)]), fill=GOLD + (255,), width=max(1, int(3 * s)))


def lock(d, x, y, col, A):
    """Значок замка, (x, y) — левый верх, ~22x30."""
    d.arc((x + 3, y, x + 19, y + 18), 180, 360, fill=col + (A,), width=4)
    d.line([(x + 3, y + 9), (x + 3, y + 13)], fill=col + (A,), width=4)
    d.line([(x + 19, y + 9), (x + 19, y + 13)], fill=col + (A,), width=4)
    d.rounded_rectangle((x, y + 12, x + 22, y + 30), 4, fill=col + (A,))


def tick_mark(d, x, y, col, A, w=6, k=1.):
    """Галочка: (x, y) — левая точка; k — доля прорисовки."""
    if k <= 0: return
    p0, p1 = (x, y), (x + 9, y + 9)
    if k < .5:
        q = k / .5; seg = [p0, (x + 9 * q, y + 9 * q)]
    else:
        q = (k - .5) / .5; seg = [p0, p1, (p1[0] + 17 * q, p1[1] - 19 * q)]
    d.line(seg, fill=col + (A,), width=w, joint='curve')


def ripple(d, t, t0, x, y):
    if t0 <= t < t0 + .5:
        k = (t - t0) / .5
        R = 22 + 50 * k
        d.ellipse((x - R, y - R, x + R, y + R), outline=WHITE + (int(220 * (1 - k)),), width=5)
        if k < .5:
            d.ellipse((x - 18, y - 18, x + 18, y + 18), fill=WHITE + (int(150 * (1 - 2 * k)),))


DEC = int(KEY[:8], 16)


def modal(t):
    """Окно «Проверка честности» — отдельным слоем (не стирает то, что под ним)."""
    ma = ramp(t, T_OPEN, T_OPEN + .3) * (1 - ramp(t, T_CLOSE, T_CLOSE + .3))
    if ma <= 0: return None
    M = Image.new('RGBA', (W, H), NAVY + (190,))
    d = ImageDraw.Draw(M)
    oy = int(50 * (1 - ease(ramp(t, T_OPEN, T_OPEN + .3))))
    def Y(v): return v + oy
    d.rounded_rectangle((190, Y(520), 890, Y(1400)), 30, fill=(27, 36, 56, 255), outline=GOLD + (255,), width=3)
    x = 222
    txt(d, (540, Y(548)), 'Проверка честности', f_mtitle, WHITE, 1, 0)
    for i, line in enumerate(('Приз и секретный ключ зашифрованы в хэш',
                              'до старта таймера — изменить их нельзя.',
                              'После разлома ключ открыт: проверь сам.')):
        txt(d, (540, Y(606 + 30 * i)), line, f_body, (210, 216, 228), 1, 0)
    txt(d, (x, Y(708)), 'ХЭШ ДО СТАРТА · SHA-256 (ПРИЗ + КЛЮЧ)', f_lbl, GOLD, 1, 0, 'lt')
    txt(d, (x, Y(736)), COMMIT[:32], f_mono, WHITE, 1, 0, 'lt')
    txt(d, (x, Y(766)), COMMIT[32:], f_mono, WHITE, 1, 0, 'lt')
    txt(d, (x, Y(812)), 'КЛЮЧ (ОТКРЫТ ПОСЛЕ РАЗЛОМА)', f_lbl, GOLD, 1, 0, 'lt')
    n = int(32 * ramp(t, T_KEY0, T_KEY1))
    if n: txt(d, (x, Y(840)), KEY[:n], f_mono, WHITE, 1, 0, 'lt')
    if t >= T_KEY1:
        txt(d, (x, Y(886)), 'ПЕРЕСЧЁТ SHA-256 (ПРИЗ + КЛЮЧ) СЕЙЧАС', f_lbl, GOLD, 1, 0, 'lt')
        n = int(64 * ramp(t, T_KEY1, T_HR1))
        if n: txt(d, (x, Y(914)), CALC[:min(n, 32)], f_mono, WHITE, 1, 0, 'lt')
        if n > 32: txt(d, (x, Y(944)), CALC[32:n], f_mono, WHITE, 1, 0, 'lt')
    if t >= T_CHECK:
        ok = CALC == COMMIT
        R = 20 * back(ramp(t, T_CHECK, T_CHECK + .3))
        d.ellipse((x + 20 - R, Y(1012) - R, x + 20 + R, Y(1012) + R), fill=(GREEN if ok else (170, 50, 50)) + (255,))
        tick_mark(d, x + 9, Y(1013), WHITE, 255, 5, ramp(t, T_CHECK + .25, T_CHECK + .55))
        txt(d, (x + 54, Y(1012)), 'Совпадает с хэшем до старта' if ok else 'Хэш НЕ совпадает!', f_row, MINT if ok else (255, 122, 122), 1, 0, 'lm')
    if t >= T_FORM:
        txt(d, (x, Y(1066)), 'КАК ВЫБРАН ПОБЕДИТЕЛЬ', f_lbl, GOLD, 1, 0, 'lt')
        txt(d, (x, Y(1094)), f'0x{KEY[:8]} = {DEC}', f_mono, WHITE, 1, 0, 'lt')
        txt(d, (x, Y(1124)), f'{DEC} mod {N_FINAL} = {WIN} → №{WIN + 1}', f_mono, WHITE, 1, 0, 'lt')
        txt(d, (x, Y(1172)), 'Список участников (заглушка) →', f_body, ORANGE, 1, 0, 'lt')
    d.rounded_rectangle((390, Y(1290), 690, Y(1366)), 38, fill=(40, 52, 78, 255), outline=GOLD + (255,), width=3)
    txt(d, (540, Y(1328)), 'Закрыть', f_close, WHITE, 1, 0, 'mm')
    ripple(d, t, T_TAP2, 540, Y(1328))
    a = np.asarray(M).copy()
    a[..., 3] = (a[..., 3].astype(np.float32) * ma).astype(np.uint8)
    return Image.fromarray(a)


def ui(t, fi):
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    draw_particles(d)
    run_ui = t < T_BREAK

    # хук 0–3 с (полоса 7–15 %)
    ha = ramp(t, .2, .6) * (1 - ramp(t, 2.7, 3.1))
    if ha > 0:
        sl = 20 * (1 - ease(ramp(t, .2, .6)))
        txt(d, (540, 172 + sl), 'Что внутри', f_hook, WHITE, ha, 10, 'mm')
        txt(d, (540, 250 + sl), 'скорлупы?', f_hook, ORANGE, ha, 10, 'mm')
    # шапка
    ba = ramp(t, 2.9, 3.4)
    if ba > 0:
        txt_parts(d, 540, 150, [('Big', WHITE), ('Balls', ORANGE)], f_brand, ba, 8)
        txt(d, (540, 244), 'Скорлупа · общий запечатанный дроп', f_sub, WHITE, ba, 6)

    if run_ui:
        ua = ramp(t, 1.6, 2.0)
        rem = 15 if t < T_RUN else max(0, math.ceil(T_BREAK - t - 1e-9))
        hot = t >= T_RUN and rem <= 3
        txt(d, (540, 585), f'00:{rem:02d}', f_timer, (255, 217, 184) if hot else WHITE, ua, 12)
        txt_parts(d, 540, 728, [('Греют: ', WHITE), (str(heaters_at(t)), GOLD)], f_heat, ua, 9)
        for x in TAPS:
            if x <= t < x + .8:
                k = (t - x) / .8
                txt(d, (770, 700 - 90 * k), '+1', f_plus, GOLD, 1 - k, 6)
        # компактная плашка «Приз запечатан · Проверить»
        sa = ramp(t, T_SEAL, T_SEAL + .3)
        if sa > 0:
            A = int(255 * sa)
            d.rounded_rectangle((250, 1150, 830, 1244), 47, fill=NAVY + (int(225 * sa),), outline=GOLD + (A,), width=3)
            s1, s2 = 'Приз запечатан · ', 'Проверить'
            w1, w2 = f_seal.getlength(s1), f_seal.getlength(s2)
            x0 = 540 - (w1 + w2 + 34) / 2
            lock(d, x0, 1164, GOLD, A)
            txt(d, (x0 + 34, 1181), s1, f_seal, WHITE, sa, 0, 'lm')
            txt(d, (x0 + 34 + w1, 1181), s2, f_seal, GOLD, sa, 0, 'lm')
            d.line([(x0 + 34 + w1, 1199), (x0 + 34 + w1 + w2, 1199)], fill=GOLD + (A,), width=2)
            short = COMMIT[:8] + '…' + COMMIT[-8:]
            n = int(len(short) * ramp(t, T_HASH0, T_HASH1))
            if n:
                txt(d, (540, 1222), ('SHA-256: ' + short[:n]).ljust(9 + len(short)), f_mono_s, (196, 202, 216), 1, 0, 'mm')
        press = max([1 - (t - x) / .15 for x in TAPS if x <= t < x + .15] or [0])
        joined = t >= JOIN + .15
        ba2 = ramp(t, 2.0, 2.4)
        if joined:
            txt(d, (540, 1395), 'Ты в списке участников', f_hint, MINT, ba2, 6, 'mm')
            button(d, t, f'Ты греешь · №{MYNUM}', ORANGE, ba2, joined=True)
        else:
            txt(d, (540, 1395), '1 нажатие = 1 участие', f_hint, WHITE, ba2, 6, 'mm')
            button(d, t, 'Греть', ORANGE, ba2, press)

    # раскрытие: приз, победитель, значок «✓ Честно»
    if t >= T_PRIZE:
        gem(d, back(ramp(t, T_PRIZE, T_PRIZE + .6)))
        txt(d, (540, 1028), 'Приз: ' + PRIZE, f_prize, GOLD, ramp(t, T_PRIZE + .2, T_PRIZE + .6), 10)
    if t >= T_WIN:
        wa = ramp(t, T_WIN, T_WIN + .3); sl = int(12 * (1 - ease(wa)))
        d.rounded_rectangle((240, 1110 + sl, 840, 1232 + sl), 28, fill=NAVY + (int(230 * wa),), outline=GOLD + (int(255 * wa),), width=3)
        txt(d, (540, 1128 + sl), 'ПОБЕДИТЕЛЬ', f_lbl, GOLD, wa, 0)
        txt_parts(d, 540, 1160 + sl, [(f'№{WIN + 1} из {N_FINAL} · ', WHITE), (WIN_TXT, ORANGE)], f_win, wa, 0)
    if t >= T_BADGE:
        ga = ramp(t, T_BADGE, T_BADGE + .3); A = int(255 * ga)
        sc = max(.01, back(ga))
        s = 'Честно · Подробнее'
        tw = f_seal.getlength(s) + 40
        hw = (tw / 2 + 36) * sc
        d.rounded_rectangle((540 - hw, 1295 - 36 * sc, 540 + hw, 1295 + 36 * sc), 36 * sc, fill=GREEN + (A,), outline=NAVY + (A,), width=3)
        if ga >= 1:
            x0 = 540 - tw / 2
            tick_mark(d, x0 + 2, 1297, WHITE, A, 6)
            txt(d, (x0 + 40, 1295), s, f_seal, WHITE, 1, 0, 'lm')
        ripple(d, t, T_TAP, 540, 1295)
    if t >= T_AGAIN:
        button(d, t, 'Повторить', GREEN, ramp(t, T_AGAIN, T_AGAIN + .4))

    M = modal(t)
    if M is not None:
        L = Image.alpha_composite(L, M); d = ImageDraw.Draw(L)

    # постоянная пометка
    d.rounded_rectangle((390, 300, 690, 340), 20, fill=ORANGE + (255,), outline=NAVY + (255,), width=3)
    txt(d, (540, 321), 'ДЕМО-ПРОТОТИП', f_badge, WHITE, 1, 0, 'mm')
    return L


# ================= ЗВУК =================
N = int(DUR * SR)
mix = np.zeros(N, np.float32)
arng = np.random.default_rng(3)


def put(t, sig):
    i = int(t * SR)
    if i >= N: return
    sig = sig[:N - i]
    mix[i:i + len(sig)] += sig


def env(n, att, dur):
    tt = np.arange(n) / SR
    e = np.minimum(1, tt / max(att, 1e-4)) * np.exp(-tt / (dur / 5))
    return e.astype(np.float32)


def tone(t, f0, f1, dur, vol, wave_='sine'):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = f0 * (f1 / f0) ** np.minimum(1, tt / (dur * .8))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) if wave_ == 'sine' else (np.sign(np.sin(ph)) * .6 if wave_ == 'square' else 2 / np.pi * np.arcsin(np.sin(ph)))
    put(t, (s * env(n, .004, dur) * vol).astype(np.float32))


def lowpass(x, k):
    return np.convolve(x, np.ones(k, np.float32) / k, mode='same')


def crackle(t, n, spread, vol):
    for _ in range(n):
        dur = .015 + arng.random() * .05; m = int(dur * SR)
        x = arng.standard_normal(m).astype(np.float32)
        x = np.diff(x, prepend=0) * .5 if arng.random() < .6 else x - lowpass(x, 6)
        put(t + arng.random() * spread, x * env(m, .001, dur) * vol * (.4 + .6 * arng.random()))


def noise_lp(t, dur, k, vol, att=.002):
    m = int(dur * SR); x = lowpass(arng.standard_normal(m).astype(np.float32), k)
    x /= np.abs(x).max() + 1e-9
    put(t, x * env(m, att, dur) * vol)


def chime(t):
    for i, (f, v) in enumerate([(880, .22), (880 * 2.76, .08), (880 * 5.4, .04), (1320, .15)]):
        tone(t + (.12 if i == 3 else 0), f, f, 2.2 - i * .3, v)


# фон: тихий гул
tt = np.arange(N) / SR
bed = (np.sin(2 * np.pi * 55 * tt) * .5 + np.sin(2 * np.pi * 82.4 * tt) * .3) * (.6 + .4 * np.sin(2 * np.pi * .25 * tt))
bed *= np.minimum(1, tt / 1.5) * np.minimum(1, (DUR - tt) / 1.5) * .05
bed[int(T_BREAK * SR):] *= .5
mix += bed.astype(np.float32)
# появление скорлупы
m = int(1.2 * SR); sw = lowpass(arng.standard_normal(m).astype(np.float32), 40)
sw *= np.sin(np.linspace(0, np.pi, m)) ** 2 / (np.abs(sw).max() + 1e-9) * .25
put(.4, sw)
# печать короткого хэша
for k in np.arange(T_HASH0, T_HASH1, .09): tone(k, 2400 + arng.random() * 400, 2400, .025, .05, 'square')
# тики (каждая смена секунды)
for s in range(int(T_RUN) + 1, int(T_BREAK)):
    hi = T_BREAK - s <= 3
    tone(s, 1760 if hi else 1180, 1760 if hi else 1180, .05, .16 if hi else .1, 'square')
# нажатия «Греть»
for x in TAPS:
    noise_lp(x, .22, 30, .18); tone(x, 300, 450, .16, .05, 'tri')
# треск стадий
crackle(T_02, 10, .3, .6)
crackle(T_03, 22, .4, .8)
for k in np.arange(T_03 + .3, T_BREAK, .05):
    p = (k - T_03) / (T_BREAK - T_03)
    if arng.random() < .2 + .5 * p: crackle(k, 2, .05, .35 + .2 * p)
# разлом
crackle(T_BREAK, 55, .5, 1.)
noise_lp(T_BREAK, .8, 8, .8)
tone(T_BREAK, 150, 36, .7, 1.)
# звон приза, победитель, значок, тапы, окно проверки
chime(T_PRIZE)
for i, f in enumerate((523, 659, 784, 1047)): tone(T_WIN + i * .09, f, f, .6, .12, 'tri')
tone(T_BADGE, 880, 1320, .18, .08, 'tri')
for x in (T_TAP, T_TAP2): noise_lp(x, .04, 3, .12); tone(x, 1500, 1500, .03, .05, 'square')
m = int(.35 * SR); sw = lowpass(arng.standard_normal(m).astype(np.float32), 25)
sw *= np.sin(np.linspace(0, np.pi, m)) / (np.abs(sw).max() + 1e-9) * .18
put(T_OPEN, sw); put(T_CLOSE, sw * .7)
for k in np.arange(T_KEY0, T_HR1, .1): tone(k, 2400 + arng.random() * 400, 2400, .025, .04, 'square')
tone(T_CHECK, 1047, 1047, .5, .18); tone(T_CHECK + .12, 1568, 1568, .9, .2)

# выравнивание: мягкий лимитер + пик -1 dBFS
mix = np.tanh(mix * 1.2) / np.tanh(1.2)
mix *= 10 ** (-1 / 20) / np.abs(mix).max()
os.makedirs(OUT, exist_ok=True)
wav_path = os.path.join(OUT, '_tmp_audio.wav')
pcm = (np.repeat(mix[:, None], 2, 1) * 32767).astype(np.int16)
with wave.open(wav_path, 'wb') as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())

# ================= ВИДЕО =================
mp4 = os.path.join(OUT, 'shell_demo.mp4')
cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
       '-i', wav_path, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
       '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', mp4]
ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
try:
    dt = 1 / FPS
    for fi in range(NF):
        t = fi / FPS
        step_particles(t, dt)
        bg = background(t).convert('RGBA')
        frame = Image.alpha_composite(bg, ui(t, fi)).convert('RGB')
        fa = .8 * ramp(t, T_BREAK, T_BREAK + .08) * (1 - ramp(t, T_BREAK + .08, T_BREAK + .6))
        if fa > 0: frame = Image.blend(frame, WARM, fa)
        ff.stdin.write(frame.tobytes())
        if fi % 150 == 0: print(f'кадр {fi}/{NF}', flush=True)
finally:
    ff.stdin.close(); rc = ff.wait()
    os.remove(wav_path)
if rc: sys.exit(f'FFmpeg завершился с кодом {rc}')
print('Готово:', mp4, '| ключ', KEY, '| SHA-256', COMMIT, '| мой №', MYNUM, '| победитель №', WIN + 1, 'из', N_FINAL)
