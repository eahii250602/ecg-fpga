# -*- coding: utf-8 -*-
"""极简版作品海报：深蓝底 + 简笔画 + 发光心电波形，美学优先"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FIG = r"D:\ecg\report\figs"
OUT_PNG = os.path.join(FIG, "poster2.png")
OUT_PDF = r"D:\ecg\docs\心衡_作品海报_极简版.pdf"

W, H = 1754, 2480
F = r"C:\Windows\Fonts\msyh.ttc"
FL = r"C:\Windows\Fonts\msyhl.ttc"      # 细体

C_TOP = (6, 14, 30)
C_BOT = (12, 30, 54)
CY = (90, 200, 255)                      # 主青色
CY2 = (40, 130, 200)
WH = (240, 248, 255)
DIM = (120, 155, 195)


def fnt(sz, light=False):
    p = FL if (light and os.path.exists(FL)) else F
    return ImageFont.truetype(p, sz)


def vgrad(w, h, c1, c2):
    a = np.array(c1, float); b = np.array(c2, float)
    r = np.linspace(0, 1, h)[:, None]
    col = a[None, :] * (1 - r) + b[None, :] * r
    return Image.fromarray(np.repeat(col[:, None, :], w, axis=1).astype(np.uint8), "RGB")


base = vgrad(W, H, C_TOP, C_BOT)

# ---- 背景网格（极淡）----
grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(grid)
for x in range(0, W, 64):
    gd.line([x, 0, x, H], fill=(70, 130, 190, 14), width=1)
for y in range(0, H, 64):
    gd.line([0, y, W, y], fill=(70, 130, 190, 14), width=1)
base = Image.alpha_composite(base.convert("RGBA"), grid)

# ---- 背景简笔画：FPGA 芯片（右上，极淡）----
art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ad = ImageDraw.Draw(art)
CX, CY0, CS = 1240, 300, 380
ad.rounded_rectangle([CX, CY0, CX + CS, CY0 + CS * 0.78], radius=18,
                     outline=(90, 170, 230, 40), width=3)
ad.rounded_rectangle([CX + 70, CY0 + 60, CX + CS - 70, CY0 + CS * 0.78 - 60], radius=8,
                     outline=(90, 170, 230, 34), width=2)
for i in range(8):                       # 引脚
    px = CX + 40 + i * (CS - 80) / 7.0
    ad.line([px, CY0 - 26, px, CY0 - 2], fill=(90, 170, 230, 34), width=3)
    ad.line([px, CY0 + CS * 0.78 + 2, px, CY0 + CS * 0.78 + 26], fill=(90, 170, 230, 34), width=3)

# ---- 背景简笔画：笔记本电脑（左下，极淡）----
LX0, LY0, LW0 = 130, 1810, 470
ad.rounded_rectangle([LX0 + 60, LY0 - 330, LX0 + LW0 - 60, LY0 - 24], radius=10,
                     outline=(90, 170, 230, 42), width=3)                       # 屏幕
ad.line([LX0 + 10, LY0 - 24, LX0 + LW0 - 10, LY0 - 24], fill=(90, 170, 230, 42), width=3)
ad.line([LX0 - 30, LY0 + 26, LX0 + LW0 + 30, LY0 + 26], fill=(90, 170, 230, 30), width=3)
ad.line([LX0 + 30, LY0 - 24, LX0 - 30, LY0 + 26], fill=(90, 170, 230, 26), width=2)
ad.line([LX0 + LW0 - 30, LY0 - 24, LX0 + LW0 + 30, LY0 + 26], fill=(90, 170, 230, 26), width=2)
base = Image.alpha_composite(base, art)


# ---- 心电波形（主视觉，发光）----
def ecg(n, beats=4, amp=1.0):
    x = np.linspace(0, 1, n)
    y = np.zeros(n)
    span = 0.90 / beats
    for k in range(beats):
        c = 0.05 + span * (k + 0.5)

        def g(off, wid, a):
            return a * np.exp(-0.5 * ((x - (c + off)) / wid) ** 2)
        y += g(-0.055, 0.010, 0.16)      # P
        y += g(-0.012, 0.0035, -0.22)    # Q
        y += g(0.0, 0.0038, 1.00)        # R
        y += g(0.014, 0.0045, -0.30)     # S
        y += g(0.075, 0.018, 0.28)       # T
    y += 0.030 * np.sin(2 * np.pi * 0.9 * x)   # 轻微基线
    return x, y * amp


n = 2600
xs, ys = ecg(n, beats=4)
X0, X1 = 120, W - 120
Y_MID, Y_AMP = 1180, 250

glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
for width, alpha in [(26, 16), (17, 26), (10, 42), (6, 70)]:
    g2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g2d = ImageDraw.Draw(g2)
    pts = [(X0 + t * (X1 - X0), Y_MID - v * Y_AMP) for t, v in zip(xs, ys)]
    g2d.line(pts, fill=CY + (alpha,), width=width, joint="curve")
    glow = Image.alpha_composite(glow, g2)
glow = glow.filter(ImageFilter.GaussianBlur(6))
base = Image.alpha_composite(base, glow)

core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
cd = ImageDraw.Draw(core)
pts = [(X0 + t * (X1 - X0), Y_MID - v * Y_AMP) for t, v in zip(xs, ys)]
cd.line(pts, fill=(200, 245, 255, 255), width=4, joint="curve")
base = Image.alpha_composite(base, core)
d = ImageDraw.Draw(base)


# ---- 文字（极少）----
def spaced(xy, s, size, col, spacing=14, anchor="ma", bold=False):
    f = fnt(size, light=not bold)
    widths = [f.getbbox(c)[2] - f.getbbox(c)[0] for c in s]
    total = sum(widths) + spacing * (len(s) - 1)
    x = xy[0] - total / 2 if anchor == "ma" else xy[0]
    for c, w in zip(s, widths):
        d.text((x, xy[1]), c, font=f, fill=col, anchor="la")
        x += w + spacing


# 标题
spaced((W // 2, 300), "心衡", 190, WH, spacing=46, bold=True, anchor="ma")
d.line([W // 2 - 150, 560, W // 2 + 150, 560], fill=CY, width=2)
d.text((W // 2, 610), "自 感 知 单 导 联 三 参 数 心 电 前 端",
       font=fnt(42), fill=DIM, anchor="ma")

# 三个关键词（波形下方）
kw = ["自感知信号质量", "单导联三参数", "全硬件定点流水线"]
ky = 1760
for i, k in enumerate(kw):
    d.text((W // 2, ky + i * 96), k, font=fnt(52), fill=WH, anchor="ma")
    if i < 2:
        d.line([W // 2 - 14, ky + i * 96 + 76, W // 2 + 14, ky + i * 96 + 76],
               fill=CY2, width=2)

# 底部技术一行
d.line([W // 2 - 320, 2130, W // 2 + 320, 2130], fill=(70, 130, 190), width=1)
d.text((W // 2, 2180), "A M D   Z Y N Q - 7 0 2 0      2 5 0   H z",
       font=fnt(30), fill=(110, 150, 195), anchor="ma")
d.text((W // 2, 2280), "一 条 导 联 · 三 个 参 数 · 一 个 可 信 度",
       font=fnt(34), fill=CY, anchor="ma")

base.convert("RGB").save(OUT_PNG)
base.convert("RGB").save(OUT_PDF, "PDF", resolution=150.0)
print("PNG:", OUT_PNG, "%.0f KB" % (os.path.getsize(OUT_PNG) / 1024))
print("PDF:", OUT_PDF, "%.2f MB" % (os.path.getsize(OUT_PDF) / 1024 / 1024))
