# -*- coding: utf-8 -*-
"""作品海报 · 工程蓝图拼版版：照片转线稿 + 多面板拼版 + 标注与图框"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FIG = r"D:\ecg\report\figs"
OUT_PNG = os.path.join(FIG, "poster4.png")
OUT_PDF = r"D:\ecg\docs\心衡_作品海报_蓝图版.pdf"

W, H = 1754, 2480
F = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"

C1 = (3, 9, 20)
C2 = (10, 26, 48)
CY = (86, 196, 255)
CY_M = (52, 132, 190)
CY_D = (30, 88, 138)
WH = (238, 247, 255)
GRY = (120, 156, 196)
GOLD = (255, 196, 92)


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


def blueprint(path, tw, th, tint=CY, strength=1.0):
    """照片 -> 青蓝线稿"""
    im = Image.open(path).convert("L")
    im = im.resize((tw, th), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(1.6))
    a = np.asarray(im, dtype=np.float32)
    gx = np.zeros_like(a); gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    mag = np.sqrt(gx * gx + gy * gy)
    mag = mag / max(mag.max(), 1e-6)
    mag = np.clip((mag ** 0.62) * 2.15 * strength, 0, 1)
    out = np.zeros((th, tw, 4), dtype=np.uint8)
    out[..., 0] = tint[0]
    out[..., 1] = tint[1]
    out[..., 2] = tint[2]
    out[..., 3] = (mag * 255).astype(np.uint8)
    art = Image.fromarray(out, "RGBA")
    glow = art.filter(ImageFilter.GaussianBlur(2.2))
    base = Image.new("RGBA", (tw, th), (8, 20, 38, 255))
    base = Image.alpha_composite(base, Image.blend(glow, glow, 0.0))
    base = Image.alpha_composite(base, glow)
    base = Image.alpha_composite(base, art)
    return base


img = vgrad(W, H, C1, C2).convert("RGBA")

# 背景网格
gr = layer(); gd = ImageDraw.Draw(gr)
for x in range(0, W, 48):
    gd.line([x, 0, x, H], fill=(58, 118, 178, 10), width=1)
for y in range(0, H, 48):
    gd.line([0, y, W, y], fill=(58, 118, 178, 10), width=1)
for x in range(0, W, 240):
    gd.line([x, 0, x, H], fill=(58, 118, 178, 18), width=1)
for y in range(0, H, 240):
    gd.line([0, y, W, y], fill=(58, 118, 178, 18), width=1)
img = Image.alpha_composite(img, gr)


def paste_panel(photo, x, y, w, h, tag, sub, tint=CY):
    """贴一张线稿面板 + 边框 + 角标 + 标题块"""
    p = blueprint(os.path.join(FIG, photo), w, h, tint=tint)
    img.paste(p, (x, y))
    d.line([x, y, x + w, y], fill=CY_M + (200,), width=2)
    d.line([x, y + h, x + w, y + h], fill=CY_M + (200,), width=2)
    d.line([x, y, x, y + h], fill=CY_M + (200,), width=2)
    d.line([x + w, y, x + w, y + h], fill=CY_M + (200,), width=2)
    for cx, cy in [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]:
        d.line([cx - 12, cy, cx + 12, cy], fill=CY, width=2)
        d.line([cx, cy - 12, cx, cy + 12], fill=CY, width=2)
    d.rounded_rectangle([x + 10, y + h - 62, x + w - 10, y + h - 10],
                        radius=6, fill=(6, 16, 32))
    d.text((x + 22, y + h - 56), tag, font=fnt(24, True), fill=CY)
    d.text((x + w - 22, y + h - 52), sub, font=fnt(18), fill=GRY, anchor="ra")


img = img.convert("RGBA")
d = ImageDraw.Draw(img)

# ================= 顶部 =================
d.text((W // 2, 62), "E C G    M O N I T O R I N G    F R O N T - E N D",
       font=fnt(22), fill=(78, 126, 172), anchor="ma")
f = fnt(186, True)
title = "心衡"
ws = [f.getbbox(c)[2] - f.getbbox(c)[0] for c in title]
x = W // 2 - (sum(ws) + 50) / 2
for c, w0 in zip(title, ws):
    d.text((x, 108), c, font=f, fill=WH)
    x += w0 + 50
d.line([W // 2 - 230, 350, W // 2 + 230, 350], fill=CY, width=2)
d.text((W // 2, 380), "自感知单导联三参数心电监测前端", font=fnt(40), fill=GRY, anchor="ma")

# ================= 主面板：现场测量 =================
paste_panel("photo5_experiment.jpg", 70, 470, 1180, 830,
            "A-01  系统全貌 · 现场测量", "SCALE 1:1")

# 主面板下方的构成说明（横向一行）
cap = "电极贴附    ·    单导联前端 AD8232    ·    分压网络 2.7k / 0.93k    ·    上位机实时显示"
d.text((72, 1312), cap, font=fnt(23), fill=CY_M)

# ================= 右侧三个小面板 =================
paste_panel("photo3_ad8232.jpg", 1350, 470, 334, 250, "A-02", "AD8232", tint=(120, 210, 255))
paste_panel("photo4_breadboard.jpg", 1350, 740, 334, 250, "A-03", "DIVIDER", tint=(255, 196, 92))
paste_panel("photo1_board_top.jpg", 1350, 1010, 334, 290, "A-04", "PYNQ-Z2", tint=CY)

# ================= 中部：心电波形带 =================
n = 2200
xs = np.linspace(0, 1, n)


def g(off, wid, a, c):
    return a * np.exp(-0.5 * ((xs - (c + off)) / wid) ** 2)


yy = np.zeros(n)
span = 0.92 / 5.0
for k in range(6):
    c = 0.05 + span * (k + 0.5)
    yy += g(-0.052, 0.0090, 0.14, c) + g(-0.012, 0.0032, -0.18, c)
    yy += g(0.0, 0.0034, 1.00, c) + g(0.013, 0.0042, -0.26, c)
    yy += g(0.070, 0.0170, 0.24, c)

X0, X1, YB, YA = 80, W - 80, 1478, 118
pts = [(X0 + u * (X1 - X0), YB - v * YA) for u, v in zip(xs, yy)]
gl = layer()
for wd_, al_ in [(20, 14), (12, 26), (7, 46), (3, 80)]:
    t_ = layer()
    ImageDraw.Draw(t_).line(pts, fill=CY + (al_,), width=wd_, joint="curve")
    gl = Image.alpha_composite(gl, t_)
img = Image.alpha_composite(img, gl.filter(ImageFilter.GaussianBlur(5)))
d = ImageDraw.Draw(img)
d.line(pts, fill=(205, 246, 255, 240), width=3, joint="curve")

# 波形左侧标签
d.text((92, 1500), "REAL-TIME  ECG  ·  250 Hz", font=fnt(22), fill=CY_M)
d.text((92, 1534), "PL 内全硬件定点流水线", font=fnt(20), fill=GRY)

# ================= 指标条 =================
stats = [("−68.5 dB", "工频抑制"), ("2000/2000", "逐位一致"), ("0.00 %", "时基误差"),
         ("70 ×", "吞吐量"), ("5.65 %", "LUT 占用"), ("+0.945 ns", "WNS")]
sy = 1600
bw = (W - 140 - 5 * 16) // 6
for i, (v, k) in enumerate(stats):
    bx = 70 + i * (bw + 16)
    d.rounded_rectangle([bx, sy, bx + bw, sy + 118], radius=8,
                        fill=(12, 30, 54), outline=CY_M + (170,), width=1)
    d.text((bx + bw // 2, sy + 34), v, font=fnt(34, True), fill=GOLD, anchor="ma")
    d.text((bx + bw // 2, sy + 84), k, font=fnt(20), fill=GRY, anchor="ma")

# ================= 三个关键词 =================
d.text((W // 2, 1770), "—  核 心 特 征  —", font=fnt(22), fill=CY_M, anchor="ma")
kws = [("自感知信号质量", "硬件给出可信度分级"), ("单导联三参数", "HR / HRV / 呼吸率"),
       ("全硬件定点流水线", "Q2.14 · 与模型逐位一致")]
for i, (k1, k2) in enumerate(kws):
    cx = 70 + i * ((W - 140) // 3) + (W - 140) // 6
    d.line([cx - 60, 1830, cx + 60, 1830], fill=CY + (200,), width=2)
    d.text((cx, 1852), k1, font=fnt(38, True), fill=WH, anchor="ma")
    d.text((cx, 1908), k2, font=fnt(22), fill=GRY, anchor="ma")

# ================= 技术图框 =================
d.line([70, 2010, W - 70, 2010], fill=CY_M + (150,), width=1)
d.text((70, 2036), "TECHNICAL  SHEET", font=fnt(20), fill=CY_D)
d.text((W - 70, 2036), "AMD ZYNQ-7020  ·  XC7Z020CLG400-1  ·  62.5 MHz  ·  250 S/s",
       font=fnt(20), fill=CY_D, anchor="ra")
d.text((W // 2, 2110), "一 条 导 联   ·   三 个 参 数   ·   一 个 可 信 度",
       font=fnt(46, True), fill=CY, anchor="ma")
d.text((W // 2, 2196), "github.com/eahii250602/ecg-fpga", font=fnt(24), fill=(88, 132, 176), anchor="ma")

# 四角十字
for cx, cy in [(40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)]:
    d.line([cx - 16, cy, cx + 16, cy], fill=CY_M + (200,), width=2)
    d.line([cx, cy - 16, cx, cy + 16], fill=CY_M + (200,), width=2)

img.convert("RGB").save(OUT_PNG)
img.convert("RGB").save(OUT_PDF, "PDF", resolution=150.0)
print("PNG:", OUT_PNG, "%.0f KB" % (os.path.getsize(OUT_PNG) / 1024))
print("PDF:", OUT_PDF, "%.2f MB" % (os.path.getsize(OUT_PDF) / 1024 / 1024))
