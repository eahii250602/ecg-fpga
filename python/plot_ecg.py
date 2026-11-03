# -*- coding: utf-8 -*-
"""画首份真实心电数据的三层视图（原始 / 去漂移 / QRS 频段）"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUTDIR = r"D:\ecg\report\figs"
os.makedirs(OUTDIR, exist_ok=True)
F = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"

raw = np.load(os.path.join(OUTDIR, "raw.npy"))
bp = np.load(os.path.join(OUTDIR, "bp.npy"))
peaks = np.load(os.path.join(OUTDIR, "peaks.npy"))
FS = 242.0
N = len(raw)

# 中间层：去漂移 + 陷波（重算一遍，与分析与一致）
def movavg(x, w):
    w = max(1, int(round(w)))
    return np.convolve(x, np.ones(w) / w, mode="same")

x = raw - movavg(raw, FS)
x = x[int(FS):-int(FS)]
w0 = 2 * np.pi * 50.0 / FS
r = 0.95
b1, b2 = -2 * np.cos(w0), 1.0
a1, a2 = -2 * r * np.cos(w0), r * r
y = np.zeros(len(x))
x1 = x2 = y1 = y2 = 0.0
for i, v in enumerate(x):
    yv = v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
    x2, x1 = x1, v
    y2, y1 = y1, yv
    y[i] = yv
mid = y

W, H = 1800, 1150
img = Image.new("RGB", (W, H), (250, 250, 247))
d = ImageDraw.Draw(img)

def txt(xy, s, size=22, color=(0, 0, 0), anchor="la", bold=False):
    f = ImageFont.truetype(FB if bold else F, size)
    d.text(xy, s, font=f, fill=color, anchor=anchor)

txt((W // 2, 26), "第一份真实人体心电数据（AD8232 + J5 + XADC）", 34, (0, 0, 0), "ma", True)
txt((W // 2, 72), "5000 点 / 20.7 秒 / 采样率约 242 Hz（软件定时，±1%）", 20, (110, 110, 110), "ma")

L, R = 90, W - 40
panel_h = 250
gaps = [120, 480, 840]
titles = [
    ("① 原始读数", "基线漂移 480 码 + 50Hz 工频 ±20 码 → 峰峰值 480 码", (200, 120, 0)),
    ("② 去基线漂移 + 50Hz 陷波", "还剩 178 码峰峰值，但主要是残余噪声", (30, 100, 160)),
    ("③ 5~15Hz 带通（QRS 波所在频段）", "只有 32 码峰峰值 = 噪声水平 → 没有心电信号", (190, 30, 30)),
]
datas = [raw, mid, bp]

for k in range(3):
    top = gaps[k]
    bot = top + panel_h
    ttl, sub, col = titles[k]
    txt((L, top - 52), ttl, 23, col, "la", True)
    txt((L, top - 26), sub, 18, (90, 90, 90), "la")
    d.rectangle([L, top, R, bot], fill=(255, 255, 255), outline=(200, 200, 200), width=2)

    sig = datas[k]
    n = len(sig)
    lo, hi = float(sig.min()), float(sig.max())
    if hi - lo < 1e-6:
        hi = lo + 1
    pad = (hi - lo) * 0.08
    lo -= pad
    hi += pad
    # 网格
    for gi in range(1, 10):
        gx = L + (R - L) * gi / 10
        d.line([(gx, top), (gx, bot)], fill=(238, 238, 238), width=1)
    for gi in range(1, 4):
        gy = top + panel_h * gi / 4
        d.line([(L, gy), (R, gy)], fill=(238, 238, 238), width=1)
    # 波形
    step = max(1, n // (R - L - 10))
    pts = []
    for px in range(L + 2, R - 2):
        i0 = int((px - L) / (R - L) * n)
        i1 = min(n, i0 + step)
        seg = sig[i0:i1]
        if len(seg) == 0:
            continue
        v = seg.min() if k == 2 else seg.mean()
        yy = bot - (v - lo) / (hi - lo) * panel_h
        pts.append((px, yy))
    if len(pts) > 1:
        d.line(pts, fill=col, width=2)
    # 刻度
    txt((L - 8, top), "%d" % round(hi), 15, (120, 120, 120), "rm")
    txt((L - 8, bot), "%d" % round(lo), 15, (120, 120, 120), "rm")

# 时间轴
for s in range(0, 21, 4):
    gx = L + (R - L) * s / 20.7
    if gx <= R:
        txt((gx, 840 + panel_h + 12), "%ds" % s, 16, (110, 110, 110), "ma")

# 结论框
d.rectangle([L, 1040, R, 1140], fill=(255, 240, 240), outline=(190, 30, 30), width=3)
txt((L + 14, 1048), "结论：这份数据里没有可用的心电信号", 24, (190, 30, 30), "la", True)
txt((L + 14, 1084), "证据：QRS 频段（5~15Hz）峰峰值仅 32 码，与噪声不可区分；自相关主峰相关系数仅 0.18（无周期）",
    19, (60, 60, 60), "la")
txt((L + 14, 1112), "但链路是通的：XADC 读数正常、能采满 5000 点、AD8232 输出中点 1.63V 稳定",
    19, (60, 60, 60), "la")

p = os.path.join(OUTDIR, "ecg_first_real.png")
img.save(p)
print("saved", p, img.size)
print("raw p2p=%d  mid p2p=%.0f  bp p2p=%.0f" % (raw.max() - raw.min(), mid.max() - mid.min(), bp.max() - bp.min()))
