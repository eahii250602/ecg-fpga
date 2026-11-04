# -*- coding: utf-8 -*-
"""作品海报 · 第五版：大字标语 + 两幅图 + 元器件点缀"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FIG = r"D:\ecg\report\figs"
OUT_PNG = os.path.join(FIG, "poster5.png")
OUT_PDF = r"D:\ecg\docs\心衡_作品海报_终版.pdf"

W, H = 1754, 2480
F = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"

C1 = (3, 9, 20)
C2 = (10, 26, 48)
CY = (86, 196, 255)
CY_M = (54, 136, 194)
CY_D = (30, 86, 134)
WH = (240, 248, 255)
GRY = (126, 160, 198)
GOLD = (255, 198, 96)


def fnt(s, b=False):
    return ImageFont.truetype(FB if b else F, s)


def vgrad(w, h, a, b):
    a = np.array(a, float); b = np.array(b, float)
    r = np.linspace(0, 1, h)[:, None]
    return Image.fromarray(
        np.repeat((a[None, :] * (1 - r) + b[None, :] * r)[:, None, :], w, axis=1)
        .astype(np.uint8), "RGB")


def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


img = vgrad(W, H, C1, C2).convert("RGBA")

# 背景网格
gr = layer(); gd = ImageDraw.Draw(gr)
for x in range(0, W, 56):
    gd.line([x, 0, x, H], fill=(58, 118, 178, 9), width=1)
for y in range(0, H, 56):
    gd.line([0, y, W, y], fill=(58, 118, 178, 9), width=1)
for x in range(0, W, 280):
    gd.line([x, 0, x, H], fill=(58, 118, 178, 16), width=1)
for y in range(0, H, 280):
    gd.line([0, y, W, y], fill=(58, 118, 178, 16), width=1)
img = Image.alpha_composite(img, gr)


# ---------------- 小元器件线描 ----------------
def comp_resistor(dr, x, y, sc=1.0, al=120):
    dr.line([x, y, x + 14 * sc, y], fill=CY + (al,), width=2)
    dr.rectangle([x + 14 * sc, y - 9 * sc, x + 54 * sc, y + 9 * sc], outline=CY + (al,), width=2)
    for k in range(3):
        bx = x + (22 + k * 10) * sc
        dr.line([bx, y - 9 * sc, bx, y + 9 * sc], fill=GOLD + (al,), width=2)
    dr.line([x + 54 * sc, y, x + 68 * sc, y], fill=CY + (al,), width=2)


def comp_cap(dr, x, y, sc=1.0, al=120):
    dr.line([x, y, x + 22 * sc, y], fill=CY + (al,), width=2)
    dr.line([x + 22 * sc, y - 13 * sc, x + 22 * sc, y + 13 * sc], fill=CY + (al,), width=3)
    dr.line([x + 31 * sc, y - 13 * sc, x + 31 * sc, y + 13 * sc], fill=CY + (al,), width=3)
    dr.line([x + 31 * sc, y, x + 53 * sc, y], fill=CY + (al,), width=2)


def comp_chip(dr, x, y, sc=1.0, al=120):
    s = 40 * sc
    dr.rectangle([x, y, x + s, y + s], outline=CY + (al,), width=2)
    dr.rectangle([x + 9 * sc, y + 9 * sc, x + s - 9 * sc, y + s - 9 * sc], outline=CY + (al - 40,), width=1)
    for k in range(3):
        px = x + (8 + k * 12) * sc
        dr.line([px, y, px, y - 10 * sc], fill=CY + (al,), width=2)
        dr.line([px, y + s, px, y + s + 10 * sc], fill=CY + (al,), width=2)


def comp_electrode(dr, x, y, sc=1.0, al=120):
    r = 18 * sc
    dr.ellipse([x - r, y - r, x + r, y + r], outline=CY + (al,), width=2)
    dr.ellipse([x - 5 * sc, y - 5 * sc, x + 5 * sc, y + 5 * sc], fill=CY + (al,))
    dr.line([x, y + r, x, y + r + 26 * sc], fill=CY + (al,), width=2)


def comp_gnd(dr, x, y, sc=1.0, al=120):
    dr.line([x, y - 22 * sc, x, y], fill=CY + (al,), width=2)
    for k, w_ in enumerate([26, 16, 7]):
        dr.line([x - w_ * sc, y + k * 7 * sc, x + w_ * sc, y + k * 7 * sc],
                fill=CY + (al,), width=2)


def comp_diode(dr, x, y, sc=1.0, al=120):
    dr.line([x, y, x + 16 * sc, y], fill=CY + (al,), width=2)
    dr.polygon([(x + 16 * sc, y - 11 * sc), (x + 16 * sc, y + 11 * sc), (x + 34 * sc, y)],
               outline=CY + (al,), width=2)
    dr.line([x + 34 * sc, y - 11 * sc, x + 34 * sc, y + 11 * sc], fill=CY + (al,), width=3)
    dr.line([x + 34 * sc, y, x + 50 * sc, y], fill=CY + (al,), width=2)


def comp_inductor(dr, x, y, sc=1.0, al=120):
    dr.line([x, y, x + 8 * sc, y], fill=CY + (al,), width=2)
    for k in range(4):
        cx = x + (16 + k * 14) * sc
        dr.arc([cx - 7 * sc, y - 7 * sc, cx + 7 * sc, y + 7 * sc], 180, 360, fill=CY + (al,), width=2)
    dr.line([x + 64 * sc, y, x + 76 * sc, y], fill=CY + (al,), width=2)


deco = layer(); dd = ImageDraw.Draw(deco)
comp_resistor(dd, 96, 214, 1.0, 105)
comp_cap(dd, 300, 206, 1.0, 100)
comp_chip(dd, 470, 196, 1.0, 100)
comp_electrode(dd, 640, 208, 0.9, 100)
comp_inductor(dd, 760, 210, 0.9, 95)
comp_diode(dd, 960, 208, 0.9, 95)
comp_gnd(dd, 1120, 214, 0.9, 95)

comp_cap(dd, 118, 1080, 1.1, 90)
comp_chip(dd, 1520, 980, 1.0, 75)
comp_resistor(dd, 1490, 1560, 1.0, 80)
comp_electrode(dd, 150, 2050, 1.0, 85)
comp_diode(dd, 1490, 2040, 1.0, 85)
comp_gnd(dd, 930, 2400, 1.0, 70)
img = Image.alpha_composite(img, deco)
d = ImageDraw.Draw(img)


# ---------------- 艺术字 ----------------
def art_text(cx, ytop, s, size, color=WH, glow=True, sp=0):
    f = fnt(size, True)
    ws = [f.getbbox(c)[2] - f.getbbox(c)[0] for c in s]
    total = sum(ws) + sp * (len(s) - 1)
    tmp = layer()
    td = ImageDraw.Draw(tmp)
    x = cx - total / 2
    for c, w_ in zip(s, ws):
        td.text((x, ytop), c, font=f, fill=color + (255,))
        x += w_ + sp
    if glow:
        g1 = tmp.filter(ImageFilter.GaussianBlur(18))
        g2 = tmp.filter(ImageFilter.GaussianBlur(6))
        out = Image.alpha_composite(g1, g2)
        out = Image.alpha_composite(out, tmp)
        img.alpha_composite(out)
    else:
        img.alpha_composite(tmp)
    return total


# 主标题
art_text(W // 2, 250, "心衡", 240, WH, glow=True, sp=56)
d.line([W // 2 - 260, 588, W // 2 + 260, 588], fill=CY + (220,), width=3)
# 完整名称
art_text(W // 2, 620, "自感知单导联三参数心电监测前端", 62, CY, glow=False, sp=6)


# ---------------- 项目全貌图（蓝图线稿） ----------------
def blueprint(path, tw, th, tint=CY, strength=1.0):
    im = Image.open(path).convert("L").resize((tw, th), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(1.5))
    a = np.asarray(im, dtype=np.float32)
    gx = np.zeros_like(a); gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    m = np.sqrt(gx * gx + gy * gy)
    m = m / max(m.max(), 1e-6)
    m = np.clip((m ** 0.55) * 1.55 * strength, 0, 1)
    out = np.zeros((th, tw, 4), np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = tint
    out[..., 3] = (m * 255).astype(np.uint8)
    art = Image.fromarray(out, "RGBA")
    gl = art.filter(ImageFilter.GaussianBlur(2.4))
    base = Image.new("RGBA", (tw, th), (7, 18, 36, 255))
    base = Image.alpha_composite(base, gl)
    return Image.alpha_composite(base, art)


PX, PY, PW, PH = 90, 730, 1574, 640
pan = blueprint(os.path.join(FIG, "photo1_board_top.jpg"), PW, PH)
img.paste(pan, (PX, PY))
d = ImageDraw.Draw(img)
for cx in (PX, PX + PW):
    d.line([cx, PY, cx, PY + PH], fill=CY_M + (210,), width=2)
for cy in (PY, PY + PH):
    d.line([PX, cy, PX + PW, cy], fill=CY_M + (210,), width=2)
for cx, cy in [(PX, PY), (PX + PW, PY), (PX, PY + PH), (PX + PW, PY + PH)]:
    d.line([cx - 16, cy, cx + 16, cy], fill=CY + (230,), width=3)
    d.line([cx, cy - 16, cx, cy + 16], fill=CY + (230,), width=3)
d.rounded_rectangle([PX + 14, PY + PH - 66, PX + 470, PY + PH - 12],
                    radius=6, fill=(6, 16, 32))
d.text((PX + 30, PY + PH - 58), "A-01   项目全貌 · 现场测量", font=fnt(26, True), fill=CY)
d.text((PX + PW - 24, PY + PH - 56), "ZYNQ-7020  ·  单导联前端", font=fnt(20), fill=GRY, anchor="ra")


# ---------------- 波形图（从图内延伸出来） ----------------
n = 2400
xs = np.linspace(0, 1, n)


def gp(off, wid, a, c):
    return a * np.exp(-0.5 * ((xs - (c + off)) / wid) ** 2)


yy = np.zeros(n)
span = 0.92 / 4.2
for k in range(5):
    c = 0.05 + span * (k + 0.55)
    yy += gp(-0.052, 0.0090, 0.15, c) + gp(-0.012, 0.0032, -0.20, c)
    yy += gp(0.0, 0.0034, 1.00, c) + gp(0.013, 0.0042, -0.28, c)
    yy += gp(0.070, 0.0170, 0.26, c)

X0, X1 = 620, W - 80
YB, YA = 1585, 138           # 波峰上探到 y≈1248，正好压在照片下边缘(1460)之上
pts = [(X0 + u * (X1 - X0), YB - v * YA) for u, v in zip(xs, yy)]
gl2 = layer()
for wd_, al_ in [(26, 14), (15, 26), (9, 48), (4, 84)]:
    t_ = layer()
    ImageDraw.Draw(t_).line(pts, fill=CY + (al_,), width=wd_, joint="curve")
    gl2 = Image.alpha_composite(gl2, t_)
img = Image.alpha_composite(img, gl2.filter(ImageFilter.GaussianBlur(7)))
d = ImageDraw.Draw(img)
d.line(pts, fill=(210, 248, 255, 250), width=4, joint="curve")

d.text((X0, YB + 34), "B-01   实时心电波形", font=fnt(26, True), fill=CY)
d.text((X0 + 310, YB + 36), "心率 75.0 BPM   ·   质量 优秀 3/3   ·   250 Hz",
       font=fnt(24), fill=GRY)


# ---------------- 三行大字标语 ----------------
slog = [("一 条 导 联", CY), ("三 个 参 数", WH), ("一 个 可 信 度", CY)]
sy = 1740
for i, (s_, col) in enumerate(slog):
    art_text(W // 2, sy + i * 152, s_, 96, col, glow=True, sp=4)


# ---------------- 底部 ----------------
d.line([W // 2 - 420, 2228, W // 2 + 420, 2228], fill=CY_M + (160,), width=1)
d.text((W // 2, 2256), "SELF-AWARE  ·  SINGLE-LEAD  ·  THREE VITALS",
       font=fnt(24), fill=CY_D, anchor="ma")
d.text((W // 2, 2312), "github.com/eahii250602/ecg-fpga",
       font=fnt(28), fill=(96, 142, 188), anchor="ma")

for cx, cy in [(48, 48), (W - 48, 48), (48, H - 48), (W - 48, H - 48)]:
    d.line([cx - 18, cy, cx + 18, cy], fill=CY_M + (190,), width=2)
    d.line([cx, cy - 18, cx, cy + 18], fill=CY_M + (190,), width=2)

img.convert("RGB").save(OUT_PNG)
img.convert("RGB").save(OUT_PDF, "PDF", resolution=150.0)
print("PNG:", OUT_PNG, "%.0f KB" % (os.path.getsize(OUT_PNG) / 1024))
print("PDF:", OUT_PDF, "%.2f MB" % (os.path.getsize(OUT_PDF) / 1024 / 1024))
