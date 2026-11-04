# -*- coding: utf-8 -*-
"""作品海报 · 蓝图美学版：心脏线描 + 心电波形 + 芯片/面包板/电极等元素"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FIG = r"D:\ecg\report\figs"
OUT_PNG = os.path.join(FIG, "poster3.png")
OUT_PDF = r"D:\ecg\docs\心衡_作品海报.pdf"

W, H = 1754, 2480
F = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"

C1 = (4, 11, 24)
C2 = (11, 28, 52)
CY = (88, 198, 255)
CY_D = (32, 110, 170)
WH = (238, 247, 255)
GRY = (118, 152, 192)
GOLD = (255, 198, 96)


def fnt(s, bold=False):
    return ImageFont.truetype(FB if bold else F, s)


def vgrad(w, h, a, b):
    a = np.array(a, float); b = np.array(b, float)
    r = np.linspace(0, 1, h)[:, None]
    col = a[None, :] * (1 - r) + b[None, :] * r
    return Image.fromarray(np.repeat(col[:, None, :], w, axis=1).astype(np.uint8), "RGB")


img = vgrad(W, H, C1, C2).convert("RGBA")


def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def glow_line(pts, color, widths_alpha, blur=7, joints=True):
    """多层叠加形成辉光"""
    g = layer()
    for wdt, al in widths_alpha:
        t = layer()
        ImageDraw.Draw(t).line(pts, fill=color + (al,), width=wdt, joint="curve")
        g = Image.alpha_composite(g, t)
    return g.filter(ImageFilter.GaussianBlur(blur))


# ---------- 网格 ----------
gr = layer()
gd = ImageDraw.Draw(gr)
for x in range(0, W, 56):
    gd.line([x, 0, x, H], fill=(60, 120, 180, 12), width=1)
for y in range(0, H, 56):
    gd.line([0, y, W, y], fill=(60, 120, 180, 12), width=1)
img = Image.alpha_composite(img, gr)

# ---------- 心脏背后的柔光 ----------
halo = layer()
hd = ImageDraw.Draw(halo)
for r, a in [(700, 10), (520, 14), (360, 20), (230, 28)]:
    hd.ellipse([400 - r, 985 - r, 400 + r, 985 + r], fill=(30, 120, 190, a))
halo = halo.filter(ImageFilter.GaussianBlur(90))
img = Image.alpha_composite(img, halo)

# ---------- 心脏轮廓 ----------
t = np.linspace(0, 2 * np.pi, 700)
hx = 16 * np.sin(t) ** 3
hy = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
SC = 19.0
HX, HY = 400, 985
heart = [(HX + hx[i] * SC, HY - hy[i] * SC) for i in range(len(t))]
img = Image.alpha_composite(img, glow_line(heart, CY, [(22, 14), (12, 26), (5, 60)], blur=8))
d = ImageDraw.Draw(img)
d.line(heart + [heart[0]], fill=(190, 240, 255, 235), width=3, joint="curve")

# ---------- 心电波形（从心脏右侧引出，贯穿画面） ----------
n = 2400
xs = np.linspace(0, 1, n)


def g(off, wid, a, c):
    return a * np.exp(-0.5 * ((xs - (c + off)) / wid) ** 2)


y = np.zeros(n)
span = 0.92 / 3.6
for k in range(4):
    c = 0.06 + span * (k + 0.55)
    y += g(-0.052, 0.0090, 0.15, c)
    y += g(-0.012, 0.0032, -0.20, c)
    y += g(0.0, 0.0034, 1.00, c)
    y += g(0.013, 0.0042, -0.28, c)
    y += g(0.070, 0.0170, 0.26, c)
y += 0.020 * np.sin(2 * np.pi * 1.1 * xs)

X0, X1 = 640, 1690
YB, YA = 985, 212
pts = [(X0 + u * (X1 - X0), YB - v * YA) for u, v in zip(xs, y)]
img = Image.alpha_composite(img, glow_line(pts, CY, [(24, 16), (14, 28), (8, 46), (4, 78)], blur=7))
d = ImageDraw.Draw(img)
d.line(pts, fill=(205, 246, 255, 255), width=4, joint="curve")

# 波形的测量游标（装饰）
for frac in (0.30, 0.60, 0.88):
    cx = X0 + frac * (X1 - X0)
    ty = YB - YA - 34
    d.line([cx, ty, cx, ty + 24], fill=(90, 175, 235, 90), width=2)
    d.line([cx - 13, ty, cx + 13, ty], fill=(90, 175, 235, 110), width=2)

# ---------- 芯片线描（右下）----------
CHX, CHY, CWS = 1330, 1430, 300
chip = layer()
cd = ImageDraw.Draw(chip)
cd.rounded_rectangle([CHX, CHY, CHX + CWS, CHY + CWS * 0.82], radius=14,
                     outline=(90, 175, 235, 120), width=3)
cd.rounded_rectangle([CHX + 58, CHY + 52, CHX + CWS - 58, CHY + CWS * 0.82 - 52],
                     radius=8, outline=(90, 175, 235, 80), width=2)
for i in range(7):
    px = CHX + 34 + i * (CWS - 68) / 6.0
    cd.line([px, CHY - 30, px, CHY - 4], fill=(90, 175, 235, 100), width=3)
    cd.line([px, CHY + CWS * 0.82 + 4, px, CHY + CWS * 0.82 + 30],
            fill=(90, 175, 235, 100), width=3)
# 芯片外接走线
traces = [
    [(CHX - 30, CHY + 60), (CHX - 150, CHY + 60), (CHX - 150, CHY - 40), (CHX - 330, CHY - 40)],
    [(CHX - 30, CHY + 140), (CHX - 110, CHY + 140), (CHX - 110, CHY + 250), (CHX - 300, CHY + 250)],
    [(CHX + CWS + 30, CHY + 90), (CHX + CWS + 150, CHY + 90), (CHX + CWS + 150, CHY + 210)],
]
for tr in traces:
    cd.line(tr, fill=(70, 150, 210, 90), width=2)
    cd.ellipse([tr[-1][0] - 6, tr[-1][1] - 6, tr[-1][0] + 6, tr[-1][1] + 6],
               fill=(90, 175, 235, 150))
chip = chip.filter(ImageFilter.GaussianBlur(0.4))
img = Image.alpha_composite(img, chip)

# ---------- 面包板线描（左下）----------
BBX, BBY, BW_, BH_ = 120, 1560, 560, 250
bb = layer()
bd = ImageDraw.Draw(bb)
bd.rounded_rectangle([BBX, BBY, BBX + BW_, BBY + BH_], radius=10,
                     outline=(70, 150, 210, 105), width=3)
for row in range(2):
    yy = BBY + 74 + row * 100
    for i in range(17):
        xx = BBX + 30 + i * (BW_ - 60) / 16.0
        bd.ellipse([xx - 5, yy - 5, xx + 5, yy + 5], fill=(80, 165, 225, 110))
# 电阻（两段折线）
for rx, ry in [(BBX + 120, BBY + 44), (BBX + 300, BBY + 44)]:
    bd.line([(rx, ry), (rx + 56, ry)], fill=(255, 198, 96, 210), width=3)
    for k in range(4):
        bd.line([(rx + 10 + k * 12, ry - 9), (rx + 10 + k * 12, ry + 9)],
                fill=(255, 198, 96, 160), width=2)
img = Image.alpha_composite(img, bb)

# ---------- 电极线描（左中，贴在心脏左下）----------
el = layer()
ed = ImageDraw.Draw(el)
for cx, cy, rr in [(250, 1290, 26), (360, 1350, 26), (470, 1290, 26)]:
    ed.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(120, 220, 255, 170), width=3)
    ed.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(120, 220, 255, 130))
    ed.line([cx, cy + rr + 4, cx, cy + rr + 46], fill=(90, 175, 235, 110), width=2)
    ed.line([cx, cy + rr + 46, BBX + 90, cy + rr + 46], fill=(90, 175, 235, 80), width=2)
img = Image.alpha_composite(img, el)
d = ImageDraw.Draw(img)


# ---------- 文字 ----------
def spaced(cx, ytop, s, size, col, sp=14, bold=False):
    f = fnt(size, bold)
    ws = [f.getbbox(c)[2] - f.getbbox(c)[0] for c in s]
    x = cx - (sum(ws) + sp * (len(s) - 1)) / 2
    for c, w in zip(s, ws):
        d.text((x, ytop), c, font=f, fill=col)
        x += w + sp


d.text((W // 2, 232), "ECG  MONITORING  FRONT-END", font=fnt(24),
       fill=(80, 130, 175), anchor="ma")
spaced(W // 2, 278, "心衡", 196, WH, sp=44, bold=True)
d.line([W // 2 - 170, 556, W // 2 + 170, 556], fill=CY, width=2)
d.text((W // 2, 598), "自 感 知 单 导 联 三 参 数 心 电 前 端",
       font=fnt(40), fill=GRY, anchor="ma")

# 三个图标 + 标签
icons_y = 1990
labels = ["自感知信号质量", "单导联三参数", "全硬件定点流水线"]
xs3 = [470, 877, 1284]
for i, (cx, lb) in enumerate(zip(xs3, labels)):
    bx = cx - 52
    by = icons_y - 52
    d.rounded_rectangle([bx, by, bx + 104, by + 104], radius=10,
                        outline=(70, 150, 210, 130), width=2)
    if i == 0:      # 心 + 脉冲
        hh = [(cx - 30, by + 40), (cx - 30, by + 62), (cx - 8, by + 44),
              (cx + 6, by + 78), (cx + 22, by + 52), (cx + 30, by + 62)]
        d.line(hh, fill=CY + (235,), width=3, joint="curve")
    elif i == 1:    # 三条参数条
        for k, hgt in enumerate([26, 40, 54]):
            d.line([cx - 28 + k * 28, by + 78, cx - 28 + k * 28, by + 78 - hgt],
                   fill=CY + (235,), width=9)
    else:           # 芯片小图
        d.rectangle([cx - 26, by + 30, cx + 26, by + 74], outline=CY + (235,), width=3)
        for k in range(4):
            px = cx - 26 + k * 17
            d.line([px, by + 30, px, by + 18], fill=CY + (200,), width=2)
            d.line([px, by + 74, px, by + 86], fill=CY + (200,), width=2)
    d.text((cx, by + 132), lb, font=fnt(34), fill=WH, anchor="ma")

d.line([W // 2 - 380, 2230, W // 2 + 380, 2230], fill=(68, 128, 180), width=1)
d.text((W // 2, 2276), "A M D   Z Y N Q - 7 0 2 0      2 5 0   H z",
       font=fnt(28), fill=(108, 150, 196), anchor="ma")
d.text((W // 2, 2352), "一条导联  ·  三个参数  ·  一个可信度",
       font=fnt(36), fill=CY, anchor="ma")

# 四角十字标记
for cx, cy in [(70, 70), (W - 70, 70), (70, H - 70), (W - 70, H - 70)]:
    d.line([cx - 18, cy, cx + 18, cy], fill=(70, 140, 200, 160), width=2)
    d.line([cx, cy - 18, cx, cy + 18], fill=(70, 140, 200, 160), width=2)

img.convert("RGB").save(OUT_PNG)
img.convert("RGB").save(OUT_PDF, "PDF", resolution=150.0)
print("PNG:", OUT_PNG, "%.0f KB" % (os.path.getsize(OUT_PNG) / 1024))
print("PDF:", OUT_PDF, "%.2f MB" % (os.path.getsize(OUT_PDF) / 1024 / 1024))
