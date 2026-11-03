# -*- coding: utf-8 -*-
"""性能基线对比：同一套滤波算法，四种实现（v2，修正两个 bug）

v1 的两个错误（已修正，记录在案）
--------------------------------
1. **浮点参考的系数在样本循环内重复计算**（`[v/Q for v in c]` 写在 for 内）
   → 浮点版被人为拖慢，导致"定点逐样本比浮点快"的荒谬结论
2. **测试信号被削顶**：心电(峰值2047) + 50Hz(600) + 漂移(300) → 求和超出 ±2048
   → 定点版饱和、浮点版不饱和 → 误差 106 LSB（真实应约 2 LSB）

四个实现
--------
  A. float_td   浮点逐样本（参考真值）
  B. fft_batch  频域批处理（离线分析的标准做法，FFT→乘 H(f)→IFFT）
  C. fixed_td   定点逐样本（**实时流式的真实成本**，与 RTL 算法完全一致）
  D. rtl        硬件流水线（1 样本/时钟，6 拍延迟，62.5 MHz）
"""
import json
import math
import os
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"D:\ecg"
OUT = os.path.join(BASE, "report", "figs")
os.makedirs(OUT, exist_ok=True)

FS = 250.0
Q = 1 << 14
FCLK = 62.5e6
RTL_LAT = 6

with open(os.path.join(BASE, "sim", "filt", "out", "filt_coef.json")) as f:
    co = json.load(f)
SECS = [(s["name"], [int(s[k]) for k in ("b0", "b1", "b2", "a1", "a2")]) for s in co["sections"]]
FCOEF = [(b0 / Q, b1 / Q, b2 / Q, a1 / Q, a2 / Q) for _, (b0, b1, b2, a1, a2) in SECS]

print("滤波器：%d 级级联（陷波50Hz + 低通40Hz），Q2.14 定点" % len(SECS))

# ---------------- 测试信号：保证不削顶 ----------------
N = 5000
t = np.arange(N) / FS
rom = []
with open(os.path.join(BASE, "python", "ecg_256x12.mem")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("//"):
            rom.append(int(line, 16) if any(c in "abcdefABCDEF" for c in line) else int(line))
rom = np.array(rom, dtype=np.float64)
if rom.max() > 2047:
    rom = rom - 2048
ecg = rom[(np.arange(N) * 2) % 256] * 0.5           # 峰值约 1024
x = ecg + 400.0 * np.sin(2 * np.pi * 50.0 * t) + 200.0 * np.sin(2 * np.pi * 0.2 * t)
pk = np.max(np.abs(x))
assert pk < 2040, "测试信号仍会削顶：%.0f" % pk
x = np.round(x)
print("测试信号：%d 点，心电×0.5 + 50Hz(400) + 0.2Hz(200)，峰值 %.0f（不削顶）" % (N, pk))


# ---------------- A. 浮点逐样本（系数已预计算） ----------------
def run_float_td(xs):
    st = [[0.0, 0.0, 0.0, 0.0] for _ in SECS]
    out = np.zeros(len(xs))
    coefs = FCOEF
    for i in range(len(xs)):
        u = xs[i]
        for k in range(len(coefs)):
            b0, b1, b2, a1, a2 = coefs[k]
            s = st[k]
            y = b0 * u + b1 * s[0] + b2 * s[1] - a1 * s[2] - a2 * s[3]
            s[0], s[1], s[2], s[3] = u, s[0], y, s[2]
            u = y
        out[i] = u
    return out


# ---------------- B. 频域批处理 ----------------
def run_fft(xs):
    X = np.fft.rfft(xs)
    f = np.fft.rfftfreq(len(xs), 1 / FS)
    H = np.ones_like(f, dtype=np.complex128)
    for b0, b1, b2, a1, a2 in FCOEF:
        z = np.exp(-2j * np.pi * f / FS)
        H *= (b0 + b1 * z + b2 * z * z) / (1 + a1 * z + a2 * z * z)
    return np.fft.irfft(X * H, n=len(xs))


# ---------------- C. 定点逐样本（与 RTL 算法一致） ----------------
def run_fixed_td(xs):
    st = [[b0, b1, b2, a1, a2, 0, 0, 0, 0] for _, (b0, b1, b2, a1, a2) in SECS]
    nsec = len(st)
    out = np.zeros(len(xs), dtype=np.int64)
    for i in range(len(xs)):
        u = int(xs[i])
        for k in range(nsec):
            s = st[k]
            acc = s[0] * u + s[1] * s[5] + s[2] * s[6] - s[3] * s[7] - s[4] * s[8]
            v = (acc + 8192) >> 14
            if v > 2047:
                v = 2047
            elif v < -2048:
                v = -2048
            s[5], s[6], s[7], s[8] = u, s[5], v, s[7]
            u = v
        out[i] = u
    return out


def best(fn, xs, rep=3):
    b, r = 1e9, None
    for _ in range(rep):
        t0 = time.perf_counter()
        r = fn(xs)
        b = min(b, time.perf_counter() - t0)
    return r, b


print("\n计时（每个实现取 3 次最好）...")
ref, tA = best(run_float_td, x);  print("  A 浮点逐样本   : %8.2f ms" % (tA * 1e3))
rB,  tB = best(run_fft, x);       print("  B 频域批处理   : %8.2f ms" % (tB * 1e3))
rC,  tC = best(run_fixed_td, x);  print("  C 定点逐样本   : %8.2f ms" % (tC * 1e3))
tD = N / FCLK;                    print("  D RTL(理论)    : %8.4f ms  (1 样本/时钟 @62.5MHz)" % (tD * 1e3))

# ---------------- 精度 ----------------
def err(a, b):
    d = np.abs(np.asarray(a, float) - np.asarray(b, float))
    return d.max(), np.sqrt((d ** 2).mean())

mC, rC_ = err(rC, ref)
mB, rB_ = err(rB, ref)
print("\n精度（相对浮点逐样本参考）")
print("  B 频域批处理 : max=%6.2f LSB  rms=%5.2f LSB  （频域法有边界效应）" % (mB, rB_))
print("  C 定点逐样本 : max=%6.2f LSB  rms=%5.2f LSB  （满量程的 %.3f%%）" % (mC, rC_, 100 * mC / 4096))

# ---------------- 汇总 ----------------
def T(sec):
    return N / sec

rows = [
    ("A 浮点逐样本（参考）", tA, T(tA), "1.0×", "离线"),
    ("B 频域批处理（FFT）", tB, T(tB), "%.1f×" % (tA / tB), "离线"),
    ("C 定点逐样本（实时等价）", tC, T(tC), "%.1f×" % (tA / tC), "**实时**"),
    ("D RTL 流水线", tD, T(tD), "%.0f×" % (tA / tD), "**硬件**"),
]
print("\n" + "=" * 80)
print("%-26s %11s %15s %9s %8s" % ("实现", "5000点耗时", "吞吐量 (S/s)", "对A加速", "性质"))
print("-" * 80)
for nm, sec, tp, sp, kind in rows:
    print("%-26s %9.2f ms %13.0f %9s %8s" % (nm, sec * 1e3, tp, sp, kind))
print("=" * 80)

print("\n实时性（ECG 只需 250 S/s）")
print("  C 定点逐样本：%.2f MS/s → 余量 %.0f 倍" % (T(tC) / 1e6, T(tC) / FS))
print("  D RTL       ：%.1f MS/s → 余量 %.0f 倍 → 单核可并行 %.0f 路 ECG" % (T(tD) / 1e6, T(tD) / FS, T(tD) / FS))
print("  RTL 延迟    ：%d 拍 = %.0f ns，占 4ms 采样周期的 %.4f%%"
      % (RTL_LAT, RTL_LAT / FCLK * 1e9, 100 * RTL_LAT / (FCLK * 4e-3)))

# ---------------- 出图 ----------------
F = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"
W, H = 1600, 920
img = Image.new("RGB", (W, H), (250, 250, 247))
d = ImageDraw.Draw(img)


def txt(xy, s, size=22, color=(0, 0, 0), anchor="la", bold=False):
    f = ImageFont.truetype(FB if bold else F, size)
    d.text(xy, s, font=f, fill=color, anchor=anchor)


txt((W // 2, 28), "同一算法的四种实现：吞吐量对比", 36, (0, 0, 0), "ma", True)
txt((W // 2, 74), "5000 点 · 陷波50Hz + 低通40Hz · Q2.14 · PC 实测（RTL 为理论值）",
    19, (110, 110, 110), "ma")

names = ["A 浮点逐样本\n(参考)", "B 频域批处理\n(不可流式)", "C 定点逐样本\n(实时等价)", "D RTL 流水线\n(实时)"]
vals = [T(tA), T(tB), T(tC), T(tD)]
cols = [(140, 140, 140), (110, 160, 205), (214, 150, 40), (190, 40, 40)]
x0, y0, pw, ph = 110, 190, 1380, 430
lg = math.log10(max(vals))
for i, (nm, v, c) in enumerate(zip(names, vals, cols)):
    bw = pw // 4 - 70
    bx = x0 + i * (pw // 4) + 35
    hh = (math.log10(v) / lg) * ph
    d.rectangle([bx, y0 + ph - hh, bx + bw, y0 + ph], fill=c)
    txt((bx + bw // 2, y0 + ph - hh - 36), "%.0f" % v, 23, c, "ma", True)
    lines = nm.split("\n")
    txt((bx + bw // 2, y0 + ph + 12), lines[0], 20, (0, 0, 0), "ma")
    txt((bx + bw // 2, y0 + ph + 40), lines[1], 17, (110, 110, 110), "ma")
d.line([(x0, y0 + ph), (x0 + pw, y0 + ph)], fill=(180, 180, 180), width=2)
txt((30, y0 - 16), "对数刻度", 15, (120, 120, 120), "la")
# 分组标注
d.line([(x0 + 20, y0 + 150), (x0 + pw // 2 - 20, y0 + 150)], fill=(200, 200, 200), width=1)
txt((x0 + 20, y0 - 40), "← 离线（要吃完整段，不能实时）", 16, (110, 160, 205), "la")
txt((x0 + pw // 2 + 20, y0 - 40), "→ 实时（逐个样本流式处理）", 16, (190, 40, 40), "la")

d.rectangle([80, 700, W - 80, 880], fill=(255, 255, 255), outline=(190, 190, 190), width=2)
txt((96, 710), "结论（可直接写进报告）", 22, (0, 0, 0), "la", True)
txt((96, 746), "1. 对「定点逐样本」——能真正跑在系统里的实时软件实现——RTL 快 %.0f 倍"
    % (T(tD) / T(tC)), 19, (40, 40, 40), "la")
txt((96, 774), "2. 对「频域批处理」快 %.1f 倍，且它需整段数据、无法流式、边界误差达 %.0f LSB（不可用于实时）"
    % (T(tD) / T(tB), mB), 19, (40, 40, 40), "la")
txt((96, 802), "3. 定点误差 max %.2f LSB（满量程 %.3f%%）；RTL 与定点模型曾逐位相同 2000/2000，故 RTL 精度同 C"
    % (mC, 100 * mC / 4096), 19, (40, 40, 40), "la")
txt((96, 830), "4. 延迟仅 %d 拍 = %.0f ns（占 4ms 采样周期的 %.4f%%）；62.5 MS/s 余量可支撑多导联/更高采样率"
    % (RTL_LAT, RTL_LAT / FCLK * 1e9, 100 * RTL_LAT / (FCLK * 4e-3)), 19, (40, 40, 40), "la")

p = os.path.join(OUT, "perf_baseline.png")
img.save(p)
print("\n图已保存:", p)
