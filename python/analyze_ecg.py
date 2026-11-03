# -*- coding: utf-8 -*-
"""首份真实心电数据分析：0.5Hz 高通 + 50Hz 陷波 + R 峰检测 + 出图"""
import os
import numpy as np

SRC = r"D:\ecg\ecg_new.txt"
OUTDIR = r"D:\ecg\report\figs"
os.makedirs(OUTDIR, exist_ok=True)

# ---------- 读数据 ----------
vals = []
with open(SRC, "r", encoding="utf-8") as f:
    for line in f:
        for t in line.strip().split(","):
            t = t.strip()
            if t:
                vals.append(int(t))
d = np.array(vals, dtype=float)
N = len(d)
print("样本数 =", N)
print("原始: min=%d max=%d mean=%.1f  p2p=%d" % (d.min(), d.max(), d.mean(), d.max() - d.min()))

FS = 242.0          # 实测采样率（由 50Hz 工频在频域的位置反推）
print("采样率估计 = %.1f Hz（±1%%）" % FS)

# ---------- 1. 高通：减去 1 秒滑动平均（≈0.5Hz 高通） ----------
W = int(round(FS))                 # 242 点
k = np.ones(W) / W
hp = d - np.convolve(d, k, mode="same")
hp = hp[W:-W]
t = np.arange(len(hp)) / FS

# ---------- 2. 50Hz 陷波（二阶 IIR） ----------
w0 = 2 * np.pi * 50.0 / FS
r = 0.95
b0, b1, b2 = 1.0, -2 * np.cos(w0), 1.0
a1, a2 = -2 * r * np.cos(w0), r * r
y = np.zeros(len(hp))
x1 = x2 = y1 = y2 = 0.0
for i, v in enumerate(hp):
    yv = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
    x2, x1 = x1, v
    y2, y1 = y1, yv
    y[i] = yv
f = y
print("滤波后: min=%.1f max=%.1f std=%.1f p2p=%.1f" % (f.min(), f.max(), f.std(), f.max() - f.min()))

# ---------- 3. R 峰检测 ----------
def detect(sig, fs, k_thr=0.45, refr=0.25):
    thr = k_thr * np.max(np.abs(sig))
    refr_n = int(refr * fs)
    peaks = []
    i = 1
    n = len(sig)
    while i < n - 1:
        if abs(sig[i]) > thr and abs(sig[i]) >= abs(sig[i - 1]) and abs(sig[i]) >= abs(sig[i + 1]):
            peaks.append(i)
            i += refr_n
        else:
            i += 1
    return np.array(peaks, dtype=int)

# 判断极性：正峰多还是负峰多
pos = np.sum(f > 0)
sig = f if pos >= len(f) - pos else -f
polarity = "正" if pos >= len(f) - pos else "负（已翻转）"
print("极性 =", polarity, " 正向样本占比 = %.1f%%" % (100.0 * max(pos, len(f) - pos) / len(f)))

peaks = detect(sig, FS)
print("检出 R 峰 = %d 个" % len(peaks))

if len(peaks) >= 2:
    rr = np.diff(peaks) / FS
    hr = 60.0 / rr
    print("RR 间期: mean=%.3f s  min=%.3f  max=%.3f  std=%.3f" % (rr.mean(), rr.min(), rr.max(), rr.std()))
    print("心率: mean=%.1f BPM  min=%.1f  max=%.1f" % (hr.mean(), hr.min(), hr.max()))
    # HRV 指标（D11 雏形）
    rmssd = np.sqrt(np.mean(np.diff(rr) ** 2)) * 1000 if len(rr) > 1 else 0.0
    sdnn = rr.std() * 1000
    pnn50 = 100.0 * np.sum(np.abs(np.diff(rr)) > 0.05) / max(1, len(rr) - 1)
    print("HRV: SDNN=%.1f ms  RMSSD=%.1f ms  pNN50=%.1f %%" % (sdnn, rmssd, pnn50))
    print("RR 序列(s):", " ".join("%.3f" % x for x in rr))
else:
    rr = np.array([])
    print("!! R 峰太少，检测失败")

# ---------- 4. 保存中间结果 ----------
np.savetxt(os.path.join(OUTDIR, "ecg_filtered.txt"), np.c_[t, f], fmt="%.4f", delimiter=",")
print("已保存滤波结果")
