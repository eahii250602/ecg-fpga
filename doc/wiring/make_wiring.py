# -*- coding: utf-8 -*-
"""生成 D3 真实心电采集的接线图（两张 PNG），v2 修正排版"""
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


def wire(d, pts, color, w=6):
    d.line(pts, fill=color, width=w, joint="curve")


def dot(d, x, y, color, r=8):
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def badge(d, x, y, n, color=BLACK):
    d.ellipse([x - 17, y - 17, x + 17, y + 17], fill=WHITE, outline=color, width=3)
    txt(d, (x, y + 1), str(n), size=21, color=color, anchor="mm", bold=True)


# ============================================================
# 图 1：分压器接线图
# ============================================================
W1, H1 = 1620, 1000
im = Image.new("RGB", (W1, H1), BG)
d = ImageDraw.Draw(im)

txt(d, (W1 // 2, 42), "D3 真实心电采集 · 分压器接线图", 37, BLACK, "ma", True)
txt(d, (W1 // 2, 92), "AD8232 输出 0~3.3V  →  分压 ÷3.9  →  XADC 输入 0~0.85V（安全）",
    21, GRAY, "ma")

# 母线
wire(d, [(250, 178), (1450, 178)], RED, 7)
txt(d, (255, 150), "3.3V 母线", 22, RED, "la", True)
txt(d, (430, 152), "← 从 PYNQ 板 3V3 排针引出（面包板上 = 插了它的那一列）", 17, RED, "la")
wire(d, [(250, 792), (1450, 792)], BLACK, 7)
txt(d, (255, 764), "GND 母线", 22, BLACK, "la", True)
txt(d, (430, 766), "← 从 PYNQ 板 GND 排针引出（面包板上 = 插了它的那一列）", 17, BLACK, "la")

# AD8232
d.rectangle([120, 245, 425, 585], fill=WHITE, outline=BLACK, width=3)
txt(d, (272, 266), "AD8232 模块", 24, BLACK, "ma", True)
txt(d, (272, 298), "（心电前端）", 17, GRAY, "ma")
for name, y in [("3V3", 315), ("SDN", 385), ("OUTPUT", 455), ("GND", 525)]:
    txt(d, (412, y), name, 21, BLACK, "rm", True)
    wire(d, [(425, y), (470, y)], BLACK, 5)
txt(d, (272, 552), "实物引脚顺序以模块印字为准", 14, GRAY, "ma")

# J5
d.rectangle([1010, 340, 1300, 700], fill=WHITE, outline=BLACK, width=3)
txt(d, (1155, 360), "PYNQ 板 J5 排针", 23, BLACK, "ma", True)
for name, y in [("1   XADC_V_P", 410), ("2   XADC_V_N", 480),
                ("3   XADCGND", 550), ("4   XADCVREF", 620)]:
    txt(d, (1022, y), name, 20, BLACK, "lm")
    wire(d, [(1010, y), (965, y)], BLACK, 5)
txt(d, (1018, 660), "第 4 脚空着不接", 17, GRAY, "lm")

# ① 3V3
wire(d, [(470, 315), (512, 315), (512, 178)], RED, 6)
dot(d, 512, 178, RED)
badge(d, 512, 258, 1, RED)
# ② SDN
wire(d, [(470, 385), (548, 385), (548, 178)], RED, 6)
dot(d, 548, 178, RED)
badge(d, 548, 330, 2, RED)
# ③ GND
wire(d, [(470, 525), (512, 525), (512, 792)], BLACK, 6)
dot(d, 512, 792, BLACK)
badge(d, 512, 580, 3, BLACK)
# ④ OUTPUT -> 2.7k
wire(d, [(470, 455), (560, 455)], BLUE, 6)
d.rectangle([560, 428, 725, 482], fill=(255, 248, 225), outline=BLUE, width=3)
txt(d, (642, 455), "2.7kΩ", 25, BLUE, "mm", True)
wire(d, [(725, 455), (775, 455)], BLUE, 6)
badge(d, 615, 400, 4, BLUE)
# ⑤ 交点 -> J5.1
dot(d, 775, 455, ORANGE, 11)
wire(d, [(775, 455), (905, 455), (905, 410), (965, 410)], ORANGE, 6)
badge(d, 905, 400, 5, ORANGE)
# ⑥ 0.93k
wire(d, [(775, 455), (775, 505)], BLACK, 6)
d.rectangle([748, 505, 802, 645], fill=(255, 248, 225), outline=BLACK, width=3)
txt(d, (738, 575), "0.93kΩ", 22, BLACK, "rm", True)
wire(d, [(775, 645), (775, 792)], BLACK, 6)
dot(d, 775, 792, BLACK)
# ⑦ J5 pin2/pin3 -> GND
wire(d, [(965, 480), (935, 480), (935, 792)], BLACK, 6)
dot(d, 935, 792, BLACK)
wire(d, [(965, 550), (900, 550), (900, 792)], BLACK, 6)
dot(d, 900, 792, BLACK)
badge(d, 935, 700, 6, BLACK)
# pin4 空
wire(d, [(965, 620), (932, 620)], GRAY, 4)
txt(d, (930, 620), "✕", 25, GRAY, "rm", True)

# 图例
d.rectangle([80, 848, 770, 980], fill=WHITE, outline=GRAY, width=2)
txt(d, (96, 860), "颜色含义", 20, BLACK, "la", True)
wire(d, [(96, 900), (146, 900)], RED, 7)
txt(d, (158, 900), "3.3V 网络", 19, BLACK, "lm")
wire(d, [(96, 940), (146, 940)], BLACK, 7)
txt(d, (158, 940), "GND 网络", 19, BLACK, "lm")
wire(d, [(420, 900), (470, 900)], BLUE, 7)
txt(d, (482, 900), "原始心电信号", 19, BLACK, "lm")
wire(d, [(420, 940), (470, 940)], ORANGE, 7)
txt(d, (482, 940), "分压后的信号", 19, BLACK, "lm")

# 警告
d.rectangle([796, 848, 1545, 980], fill=(255, 235, 238), outline=RED, width=3)
txt(d, (812, 860), "安全红线：两条绝对不能错", 21, RED, "la", True)
txt(d, (812, 900), "① 2.7k 接信号侧、0.93k 接地侧", 19, BLACK, "la")
txt(d, (812, 928), "   装反 → 输出 2.45V，会烧 XADC", 19, RED, "la")
txt(d, (812, 958), "② AD8232 只能接 3.3V，接 5V 会超量程", 19, BLACK, "la")

p1 = os.path.join(OUT, "01_分压器接线图.png")
im.save(p1)

# ============================================================
# 图 2：面包板插法
# ============================================================
W2, H2 = 1200, 800
im2 = Image.new("RGB", (W2, H2), BG)
d2 = ImageDraw.Draw(im2)

txt(d2, (W2 // 2, 40), "面包板怎么插（俯视图）", 35, BLACK, "ma", True)

# 板体
d2.rounded_rectangle([320, 110, 880, 620], radius=16, fill=(242, 240, 232),
                     outline=(120, 120, 110), width=3)

COLS, ROWS = 8, 3
x0, dx = 380, 62
y0, dy = 280, 70
ROWS_L = ["a", "b", "c"]

for ci in range(COLS):
    x = x0 + ci * dx
    txt(d2, (x, 248), str(ci + 1), 17, GRAY, "mm")
    for ri in range(ROWS):
        y = y0 + ri * dy
        d2.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(202, 200, 192),
                   outline=(150, 148, 140))
for ri, rn in enumerate(ROWS_L):
    txt(d2, (352, y0 + ri * dy), rn, 19, GRAY, "rm")

# 高亮第 5 列（交点所在列）
x_j = x0 + 4 * dx
d2.rounded_rectangle([x_j - 22, y0 - 26, x_j + 22, y0 + 2 * dy + 26],
                     radius=10, outline=GREEN, width=3)


def resistor_h(dd, xa, xb, y, label):
    dd.line([(xa, y), (xa + 24, y)], fill=(70, 70, 70), width=5)
    dd.line([(xb - 24, y), (xb, y)], fill=(70, 70, 70), width=5)
    dd.rectangle([xa + 24, y - 12, xb - 24, y + 12], fill=BODY,
                 outline=(90, 80, 60), width=2)
    for k, cc in enumerate([(150, 30, 30), (30, 30, 150), (200, 160, 20)]):
        cx = xa + 30 + k * 13
        dd.rectangle([cx, y - 12, cx + 7, y + 12], fill=cc)
    txt(dd, ((xa + xb) / 2, y - 34), label, 20, BLACK, "mm", True)


# 2.7k：第1列 a -> 第5列 a
yA = y0
resistor_h(d2, x0 + 0 * dx, x0 + 4 * dx, yA, "2.7kΩ")
# 0.93k：第5列 b -> 第7列 b
yB = y0 + 1 * dy
resistor_h(d2, x0 + 4 * dx, x0 + 6 * dx, yB, "0.93kΩ")

# 左侧：接 AD8232 OUTPUT
d2.line([(150, yA), (x0, yA)], fill=BLUE, width=5)
d2.polygon([(150, yA), (168, yA - 9), (168, yA + 9)], fill=BLUE)
txt(d2, (146, yA), "AD8232 的 OUTPUT", 20, BLUE, "rm", True)

# 右侧：交点 -> J5 第1脚
yC = y0 + 2 * dy
d2.line([(x_j, yC), (1080, yC)], fill=ORANGE, width=5)
d2.polygon([(1080, yC), (1062, yC - 9), (1062, yC + 9)], fill=ORANGE)
txt(d2, (1090, yC), "J5", 20, ORANGE, "lm", True)
txt(d2, (1090, yC + 24), "第1脚", 20, ORANGE, "lm", True)

# 下侧：0.93k 右腿 -> GND
x_g = x0 + 6 * dx
d2.line([(x_g, yB), (x_g, 690)], fill=BLACK, width=5)
d2.polygon([(x_g, 690), (x_g - 9, 672), (x_g + 9, 672)], fill=BLACK)
txt(d2, (x_g + 16, 700), "接 GND", 20, BLACK, "lm", True)

# 说明
d2.rectangle([80, 110, 300, 620], fill=WHITE, outline=GRAY, width=2)
txt(d2, (96, 126), "怎么看这张图", 19, BLACK, "la", True)
txt(d2, (96, 164), "1. 同一列的", 18, BLACK, "la")
txt(d2, (96, 190), "   a/b/c 三个孔", 18, BLACK, "la")
txt(d2, (96, 216), "   内部是通的", 18, BLACK, "la")
txt(d2, (96, 252), "2. 一个电阻的", 18, BLACK, "la")
txt(d2, (96, 278), "   两条腿必须插", 18, BLACK, "la")
txt(d2, (96, 304), "   在不同列", 18, BLACK, "la")
txt(d2, (96, 340), "3. 两个电阻的", 18, BLACK, "la")
txt(d2, (96, 366), "   交点：都插在", 18, BLACK, "la")
txt(d2, (96, 392), "   第 5 列（绿框）", 18, GREEN, "la")
txt(d2, (96, 428), "4. 插在同一列", 18, BLACK, "la")
txt(d2, (96, 454), "   = 短路，电阻", 18, BLACK, "la")
txt(d2, (96, 480), "   就不起作用了", 18, RED, "la")

p2 = os.path.join(OUT, "02_面包板插法.png")
im2.save(p2)

print("saved:", p1)
print("saved:", p2)
for p in (p1, p2):
    print(os.path.basename(p), Image.open(p).size)