# -*- coding: utf-8 -*-
"""面包板插法图（v3：说明框移到下方，左边留空给导线）"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\ecg\doc\wiring"
os.makedirs(OUT, exist_ok=True)

F  = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"

RED    = (211, 47, 47)
BLACK  = (33, 33, 33)
BLUE   = (21, 101, 192)
ORANGE = (239, 108, 0)
GRAY   = (140, 140, 140)
GREEN  = (46, 125, 50)
WHITE  = (255, 255, 255)
BG     = (250, 250, 247)
BODY   = (232, 214, 176)


def txt(d, xy, s, size=22, color=BLACK, anchor="la", bold=False):
    f = ImageFont.truetype(FB if bold else F, size)
    d.text(xy, s, font=f, fill=color, anchor=anchor)


W, H = 1200, 800
im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)

txt(d, (W // 2, 38), "面包板怎么插（俯视图）", 36, BLACK, "ma", True)

# 板体
d.rounded_rectangle([330, 110, 880, 600], radius=16, fill=(242, 240, 232),
                    outline=(120, 120, 110), width=3)

COLS, ROWS = 8, 3
x0, dx = 380, 62
y0, dy = 270, 70
ROWS_L = ["a", "b", "c"]

for ci in range(COLS):
    x = x0 + ci * dx
    txt(d, (x, 238), str(ci + 1), 17, GRAY, "mm")
    for ri in range(ROWS):
        y = y0 + ri * dy
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(202, 200, 192),
                  outline=(150, 148, 140))
for ri, rn in enumerate(ROWS_L):
    txt(d, (352, y0 + ri * dy), rn, 19, GRAY, "rm")

# 高亮第 5 列
x_j = x0 + 4 * dx
d.rounded_rectangle([x_j - 23, y0 - 27, x_j + 23, y0 + 2 * dy + 27],
                    radius=10, outline=GREEN, width=3)
txt(d, (x_j, 600 - 6), "交点在这一列", 16, GREEN, "ma", True)


def resistor_h(dd, xa, xb, y, label):
    dd.line([(xa, y), (xa + 24, y)], fill=(70, 70, 70), width=5)
    dd.line([(xb - 24, y), (xb, y)], fill=(70, 70, 70), width=5)
    dd.rectangle([xa + 24, y - 12, xb - 24, y + 12], fill=BODY,
                 outline=(90, 80, 60), width=2)
    for k, cc in enumerate([(150, 30, 30), (30, 30, 150), (200, 160, 20)]):
        cx = xa + 30 + k * 13
        dd.rectangle([cx, y - 12, cx + 7, y + 12], fill=cc)
    dd.text(((xa + xb) / 2, y - 34), label,
            font=ImageFont.truetype(FB, 20), fill=BLACK, anchor="mm")


yA = y0
resistor_h(d, x0 + 0 * dx, x0 + 4 * dx, yA, "2.7kΩ")
yB = y0 + 1 * dy
resistor_h(d, x0 + 4 * dx, x0 + 6 * dx, yB, "0.93kΩ")

# 左：AD8232 OUTPUT
d.line([(40, yA), (x0, yA)], fill=BLUE, width=5)
d.polygon([(x0, yA), (x0 - 18, yA - 9), (x0 - 18, yA + 9)], fill=BLUE)
txt(d, (40, yA - 30), "AD8232 的 OUTPUT", 20, BLUE, "lm", True)

# 右：交点 -> J5 第 1 脚
yC = y0 + 2 * dy
d.line([(x_j, yC), (1050, yC)], fill=ORANGE, width=5)
d.polygon([(1050, yC), (1032, yC - 9), (1032, yC + 9)], fill=ORANGE)
txt(d, (1062, yC - 10), "J5 第 1 脚", 20, ORANGE, "lm", True)
txt(d, (1062, yC + 16), "（XADC_V_P）", 16, ORANGE, "lm")

# 下：0.93k 右腿 -> GND
x_g = x0 + 6 * dx
d.line([(x_g, yB), (x_g, 640)], fill=BLACK, width=5)
d.polygon([(x_g, 640), (x_g - 9, 622), (x_g + 9, 622)], fill=BLACK)
txt(d, (x_g + 18, 630), "接 GND", 20, BLACK, "lm", True)

# 底部说明
d.rectangle([48, 660, 1152, 782], fill=WHITE, outline=GRAY, width=2)
txt(d, (66, 668), "① 同一列的 a / b / c 三个孔，内部是连通的 —— 一列就是一个「节点」",
    19, BLACK, "la")
txt(d, (66, 700), "② 一个电阻的两条腿必须插在【不同列】；插在同一列 = 把电阻短路，等于没接",
    19, BLACK, "la")
txt(d, (66, 732), "③ 两个电阻的交点：2.7k 的右腿和 0.93k 的左腿【都插在第 5 列】→ 它们自动连通",
    19, BLACK, "la")
txt(d, (66, 760), "　（绿框那一列）", 18, GREEN, "la")

p = os.path.join(OUT, "02_面包板插法.png")
im.save(p)
print("saved:", p, Image.open(p).size)