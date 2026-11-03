# -*- coding: utf-8 -*-
"""心电分析 v2：Pan-Tompkins 风格 R 峰检测 + 自相关交叉验证"""
import os
import numpy as np

SRC = r"D:\ecg\ecg_new.txt"
OUTDIR = r"D:\ecg\report\figs"
os.makedirs(OUTDIR, exist_ok=True)

vals = []
with open(SRC, "r", encoding="utf-8") as f:
    for line in f:
        for t in line.strip().split(","):
            if t.strip():
                vals.append(int(t))
d = np.array(vals, dtype=float)
N = len(d)
FS = 242.0
print("样本 %d 点  %.1f s  @%.0f Hz" % (N, N / FS, FS))
print("原始 p2p = %d 码（主要是基线漂移）" % (d.max() - d.min()))


def movavg(x, w):
    w = max(1, int(round(w)))
    return np.convolve(x, np.ones(w) / w, mode="same")


# ---- 1. 去基线（0.5Hz 高通） ----
x = d - movavg(d, FS)
x = x[int(FS):-int(FS)]

# ---- 2. 50Hz 陷波 ----
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
x = y
print("去基线+陷波后 std = %.1f 码" % x.std())

# ---- 3. 带通 5~15Hz（两级滑动平均实现） ----
bp = x - movavg(x, FS / 5.0)      # 高通 ~5Hz
bp = movavg(bp, FS / 15.0)        # 低通 ~15Hz
print("5~15Hz 带通后 std = %.1f 码  p2p = %.1f" % (bp.std(), bp.max() - bp.min()))

# ---- 4. 自相关：找周期（不依赖准确的 fs） ----
seg = bp[len(bp) // 4: 3 * len(bp) // 4]
seg = seg - seg.mean()
ac = np.correlate(seg, seg, mode="full")[len(seg) - 1:]
ac = ac / ac[0]
lag_min, lag_max = int(0.33 * FS), int(2.0 * FS)     # 30~180 BPM
lag = lag_min + int(np.argmax(ac[lag_min:lag_max]))
print("自相关主峰 lag = %d 点 = %.3f s -> %.1f BPM (corr=%.2f)"
      % (lag, lag / FS, 60.0 * FS / lag, ac[lag]))

# ---- 5. Pan-Tompkins 包络 ----
df = np.diff(bp, prepend=bp[0])
sq = df ** 2
env = movavg(sq, 0.15 * FS)
env = env / env.max()

peaks = []
refr = int(0.25 * FS)
thr = 0.30
i = 1
while i < len(env) - 1:
    if env[i] > thr and env[i] >= env[i - 1] and env[i] >= env[i + 1]:
        # 在原始带通信号上找这一拍的真实极值位置
        a = max(0, i - int(0.08 * FS))
        b = min(len(bp) - 1, i + int(0.08 * FS))
        j = a + int(np.argmax(np.abs(bp[a:b + 1])))
        peaks.append(j)
        i += refr
    else:
        i += 1
peaks = np.array(peaks)

# 判断极性：看 R 峰处 bp 的正负
if len(peaks) > 3:
    signed = bp[peaks]
    if np.sum(signed < 0) > len(signed) / 2:
        bp = -bp
        env = env
        print("极性：原始为倒置，已翻转用于显示")
    else:
        print("极性：正向")

print("检出 R 峰 = %d 个" % len(peaks))
print("峰位（秒）:", " ".join("%.2f" % (p / FS) for p in peaks))

if len(peaks) >= 3:
    rr = np.diff(peaks) / FS
    hr = 60.0 / rr
    print("RR: mean=%.3f s  std=%.3f  min=%.3f  max=%.3f" % (rr.mean(), rr.std(), rr.min(), rr.max()))
    print("心率: %.1f BPM (范围 %.1f ~ %.1f)" % (hr.mean(), hr.min(), hr.max()))
    # 剔除明显异常（>2x 中位数）后重算
    med = np.median(rr)
    good = rr[(rr > 0.5 * med) & (rr < 1.5 * med)]
    print("中等 RR = %.3f s -> %.1f BPM" % (med, 60.0 / med))
    print("剔除异常后 RR: n=%d mean=%.3f std=%.3f -> %.1f BPM"
          % (len(good), good.mean(), good.std(), 60.0 / good.mean()))
    if len(good) > 2:
        print("SDNN=%.1f ms" % (good.std() * 1000))
        print("RMSSD=%.1f ms" % (np.sqrt(np.mean(np.diff(good) ** 2)) * 1000))
        print("pNN50=%.1f %%" % (100.0 * np.sum(np.abs(np.diff(good)) > 0.05) / max(1, len(good) - 1)))

np.save(os.path.join(OUTDIR, "bp.npy"), bp)
np.save(os.path.join(OUTDIR, "env.npy"), env)
np.save(os.path.join(OUTDIR, "peaks.npy"), peaks)
np.save(os.path.join(OUTDIR, "raw.npy"), d)
print("已保存中间结果到", OUTDIR)
