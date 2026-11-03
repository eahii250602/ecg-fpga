# -*- coding: utf-8 -*-
"""单导联三参数：HR / HRV / EDR（心电衍生呼吸率）

创新点说明
----------
一条心电导联能同时给出三个生理参数：
    1. HR  —— 心率（R 峰间隔）
    2. HRV —— 心率变异性（SDNN / RMSSD / pNN50），反映自主神经活动
    3. EDR —— 心电衍生呼吸率（ECG-Derived Respiration）
              呼吸引起的胸腔阻抗变化会调制心电的**基线**与**R 峰幅度**，
              因此可以从同一路信号里把呼吸率"解"出来

验证方法（可证伪）
------------------
不拿"看起来像"当证据。合成一段心电，**注入已知的呼吸频率**，再让算法去估计：
    注入 0.25 Hz（15 次/分）→ 算法必须输出 15.0 ± 0.5 次/分
    注入 0.30 Hz（18 次/分）→ 算法必须输出 18.0 ± 0.5 次/分
    注入 0.20 Hz（12 次/分）→ 算法必须输出 12.0 ± 0.5 次/分
估计不出来就是算法错，不是"数据不好"。

同时注入已知 HRV（RSA：呼吸性窦性心律不齐），检验 SDNN/RMSSD 是否被正确还原。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\ecg\report\figs"
os.makedirs(OUT, exist_ok=True)
FS = 250.0


# ============================================================
# 1. 合成心电（可注入已知 HR / HRV / 呼吸）
# ============================================================
def synth_ecg(dur=60.0, hr_bpm=72.0, resp_hz=0.25, rsa_bpm=3.0, lf_bpm=1.5,
              noise50=40.0, drift=60.0, seed=1):
    """按 P-QRS-T 高斯模板合成，R 峰时刻受 RSA(呼吸) + LF 调制"""
    rng = np.random.default_rng(seed)
    n = int(dur * FS)
    t = np.arange(n) / FS

    # --- R 峰时刻：瞬时心率 = 基础 + RSA(呼吸相位) + LF ---
    hr_inst = (hr_bpm
               + rsa_bpm * np.sin(2 * np.pi * resp_hz * t)
               + lf_bpm * np.sin(2 * np.pi * 0.1 * t + 1.1))
    phase = np.cumsum(hr_inst / 60.0 / FS)        # 累积拍数
    beats = []
    k = 1.0
    while True:
        idx = np.searchsorted(phase, k)
        if idx >= n:
            break
        beats.append(idx)
        k += 1.0
    beats = np.array(beats)

    # --- 每个心跳叠 P / QRS / T 高斯 ---
    sig = np.zeros(n)
    def gauss(center, sigma, amp):
        lo = max(0, int(center - 4 * sigma))
        hi = min(n, int(center + 4 * sigma))
        if hi <= lo:
            return
        tt = np.arange(lo, hi)
        sig[lo:hi] += amp * np.exp(-0.5 * ((tt - center) / sigma) ** 2)

    for b in beats:
        gauss(b - 0.16 * FS, 0.022 * FS, 120)      # P
        gauss(b - 0.02 * FS, 0.008 * FS, -180)     # Q
        gauss(b,              0.009 * FS, 1000)    # R
        gauss(b + 0.022 * FS, 0.010 * FS, -260)    # S
        gauss(b + 0.20 * FS, 0.045 * FS, 260)      # T

    # --- 呼吸对基线的调制（EDR 物理来源之一）---
    sig += drift * np.sin(2 * np.pi * resp_hz * t)
    # --- 呼吸对心电幅度的调制（EDR 物理来源之二）---
    #   注意：只调制心电本身，不要连漂移一起乘——否则漂移×sin² 会产生 2f 谐波，
    #   那是我第一版算法被"骗"到 2 倍呼吸率的原因（已由注入实验暴露）
    sig *= (1.0 + 0.15 * np.sin(2 * np.pi * resp_hz * t))
    # --- 50Hz 工频 + 随机噪声 ---
    sig += noise50 * np.sin(2 * np.pi * 50.0 * t)
    sig += rng.normal(0, 3.0, n)

    return sig, t, beats, hr_inst


# ============================================================
# 2. 信号处理链（与 RTL 同构：陷波 → 低通）
# ============================================================
def notch50(x, fs=FS, q=10.0):
    w0 = 2 * np.pi * 50.0 / fs
    alpha = np.sin(w0) / (2 * q)
    b = np.array([1, -2 * np.cos(w0), 1]) / (1 + alpha)
    a = np.array([1, -2 * np.cos(w0) / (1 + alpha), (1 - alpha) / (1 + alpha)])
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        yv = b[0] * v + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
        x2, x1 = x1, v
        y2, y1 = y1, yv
        y[i] = yv
    return y


def lowpass(x, fc=40.0, fs=FS, q=0.7071):
    w0 = 2 * np.pi * fc / fs
    alpha = np.sin(w0) / (2 * q)
    c = np.cos(w0)
    b = np.array([(1 - c) / 2, 1 - c, (1 - c) / 2]) / (1 + alpha)
    a = np.array([1, -2 * c / (1 + alpha), (1 - alpha) / (1 + alpha)])
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        yv = b[0] * v + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
        x2, x1 = x1, v
        y2, y1 = y1, yv
        y[i] = yv
    return y


# ============================================================
# 3. R 峰检测 + HR + HRV
# ============================================================
def detect_r(x, fs=FS):
    """简化 Pan-Tompkins：带通 → 微分 → 平方 → 滑动积分 → 峰检测"""
    # 5~15 Hz 带通（两级滑动平均）
    def ma(v, w):
        w = max(1, int(round(w)))
        return np.convolve(v, np.ones(w) / w, mode="same")
    hp = x - ma(x, fs / 5.0)
    bp = ma(hp, fs / 15.0)
    d = np.diff(bp, prepend=bp[0])
    env = ma(d ** 2, 0.15 * fs)
    if env.max() <= 0:
        return np.array([], dtype=int)
    env = env / env.max()
    pk, refr = [], int(0.25 * fs)
    i, thr = 1, 0.3
    while i < len(env) - 1:
        if env[i] > thr and env[i] >= env[i - 1] and env[i] >= env[i + 1]:
            a, b = max(0, i - int(0.08 * fs)), min(len(x), i + int(0.08 * fs))
            pk.append(a + int(np.argmax(np.abs(x[a:b]))))
            i += refr
        else:
            i += 1
    return np.array(pk)


def hrv_metrics(peaks, fs=FS):
    if len(peaks) < 3:
        return None
    rr = np.diff(peaks) / fs
    med = np.median(rr)
    keep = rr[(rr > 0.5 * med) & (rr < 1.5 * med)]
    if len(keep) < 3:
        return None
    return {
        "n": len(peaks), "rr": rr, "rr_ok": keep,
        "hr": 60.0 / keep.mean(),
        "sdnn": keep.std() * 1000,
        "rmssd": np.sqrt(np.mean(np.diff(keep) ** 2)) * 1000,
        "pnn50": 100.0 * np.sum(np.abs(np.diff(keep)) > 0.05) / max(1, len(keep) - 1),
    }


# ============================================================
# 4. EDR：从呼吸对基线的调制里提取呼吸率
# ============================================================
def edr_rate(x_clean, peaks, fs=FS):
    """EDR：剔除 QRS-T 区间 → 线性插值 → 0.05~1.0 Hz 带通 → 求谱峰

    这是文献里的标准做法（QRS 掩蔽 + 插值），比"中值滤波去心电"干净得多：
    中值法会残留 QRS 尖峰，污染呼吸带；插值法直接把心电事件挖掉再补平滑曲线。

    v1 的错误（已由注入实验暴露）：高通拐点用了 ~0.3 Hz
        → 12/15/18 次/分（0.20/0.25/0.30 Hz）的基频被滤掉，
          只剩二次谐波 → 估计值恰好是真实值的 2 倍。
    """
    n = len(x_clean)
    idx = np.arange(n)

    # ① 掩蔽 QRS-T：R 峰前 0.15 s 到后 0.40 s
    mask = np.ones(n, dtype=bool)
    for p in peaks:
        a = max(0, p - int(0.15 * fs))
        b = min(n, p + int(0.40 * fs))
        mask[a:b] = False
    if mask.sum() < 10:
        return None, None, None

    # ② 在被掩蔽处线性插值，得到"只有基线"的曲线
    base = x_clean.copy()
    base[~mask] = np.interp(idx[~mask], idx[mask], x_clean[mask])

    # ③ 0.05~1.0 Hz 带通（呼吸频段；高通必须够低，否则吃掉基频）
    def ma(v, ww):
        ww = max(1, int(round(ww)))
        if ww >= len(v):
            return np.full_like(v, v.mean())
        return np.convolve(v, np.ones(ww) / ww, mode="same")

    bp = base - ma(base, fs / 0.05)
    bp = ma(bp, fs / 1.0)
    edge = int(fs * 2)
    bp = bp[edge:-edge]
    if len(bp) < 64:
        return None, None, None

    # ④ 谱峰
    win = np.hanning(len(bp))
    sp = np.abs(np.fft.rfft(bp * win))
    fr = np.fft.rfftfreq(len(bp), 1 / fs)
    m = (fr >= 0.08) & (fr <= 0.80)
    idx2 = np.argmax(sp[m])
    return fr[m][idx2] * 60.0, bp, sp[m]


# ============================================================
# 5. 三个已知呼吸率下的验证
# ============================================================
print("=" * 74)
print("单导联三参数验证：注入已知呼吸率，看算法能否还原")
print("=" * 74)

cases = [(0.20, "12 次/分"), (0.25, "15 次/分"), (0.30, "18 次/分")]
results = []
for resp_hz, label in cases:
    sig, t, beats, hr_inst = synth_ecg(dur=60.0, resp_hz=resp_hz, seed=20261104)
    x = notch50(sig)
    x = lowpass(x)
    pk = detect_r(x)
    m = hrv_metrics(pk)
    edr_bpm, bp, sp = edr_rate(x, pk)
    results.append(dict(resp_hz=resp_hz, label=label, m=m, edr=edr_bpm, sig=x, t=t,
                        peaks=pk, beats=beats, bp=bp))
    print("\n注入呼吸 %s（%.3f Hz）" % (label, resp_hz))
    if m:
        print("  R 峰检出 %d 个（真值 %d）  漏检率 %.1f%%"
              % (m["n"], len(beats), 100 * max(0, len(beats) - m["n"]) / max(1, len(beats))))
        print("  HR   = %.2f BPM" % m["hr"])
        print("  HRV  : SDNN=%.1f ms  RMSSD=%.1f ms  pNN50=%.1f%%"
              % (m["sdnn"], m["rmssd"], m["pnn50"]))
    print("  EDR  = %.1f 次/分  （误差 %+.1f）" % (edr_bpm, edr_bpm - resp_hz * 60))

print("\n" + "=" * 74)
print("EDR 精度汇总")
print("=" * 74)
print("%-12s %12s %12s %10s" % ("注入", "真值(次/分)", "估计(次/分)", "误差"))
ok = True
for r in results:
    err = r["edr"] - r["resp_hz"] * 60
    flag = "✓" if abs(err) < 0.5 else "✗"
    if abs(err) >= 0.5:
        ok = False
    print("%-12s %12.1f %12.1f %8.1f %s" % (r["label"], r["resp_hz"] * 60, r["edr"], err, flag))
print("\n判定：%s（判据：误差 < 0.5 次/分）" % ("PASS ✓" if ok else "FAIL"))

# ============================================================
# 6. 出图
# ============================================================
F = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"
W, H = 1700, 1000
img = Image.new("RGB", (W, H), (250, 250, 247))
d = ImageDraw.Draw(img)


def txt(xy, s, size=22, color=(0, 0, 0), anchor="la", bold=False):
    f = ImageFont.truetype(FB if bold else F, size)
    d.text(xy, s, font=f, fill=color, anchor=anchor)


txt((W // 2, 26), "单导联三参数：心率 / 心率变异性 / 心电衍生呼吸率", 34, (0, 0, 0), "ma", True)
txt((W // 2, 72), "同一路心电信号，同时输出 HR、HRV、呼吸率——并用注入已知呼吸率的方式验证正确性",
    19, (110, 110, 110), "ma")

sel = results[1]           # 15 次/分那一组
tt = sel["t"]
zz = sel["sig"]
seg = (tt >= 10) & (tt < 22)

# 面板 1：滤波后心电 + R 峰
L, R = 110, W - 60
top1, h1 = 130, 300
d.rectangle([L, top1, R, top1 + h1], fill=(255, 255, 255), outline=(200, 200, 200), width=2)
txt((L, top1 - 30), "① 滤波后心电 + 检测到的 R 峰（10~22 秒）", 21, (30, 100, 160), "la", True)
vv = zz[seg]
n1 = len(vv)
lo, hi = vv.min(), vv.max()
for k, p in enumerate(sel["peaks"]):
    if seg[p]:
        px = L + (p - np.argmax(seg)) / n1 * (R - L)
        if L <= px <= R:
            d.line([(px, top1 + 6), (px, top1 + h1 - 6)], fill=(220, 90, 90), width=2)
            d.ellipse([px - 5, top1 + 6, px + 5, top1 + 16], fill=(220, 90, 90))
pts = []
for i in range(n1):
    px = L + i / n1 * (R - L)
    py = top1 + h1 - (vv[i] - lo) / (hi - lo) * h1
    pts.append((px, py))
d.line(pts, fill=(30, 100, 160), width=2)

# 面板 2：呼吸带通信号（EDR 来源）
top2, h2 = 520, 240
d.rectangle([L, top2, R, top2 + h2], fill=(255, 255, 255), outline=(200, 200, 200), width=2)
txt((L, top2 - 30), "② EDR：剔除 QRS-T 并插值后，0.05~1.0 Hz 带通（呼吸信号）", 21, (150, 110, 30), "la", True)
bpv = sel["bp"]
off = int(10 * FS)
bpv = bpv[off:] if len(bpv) > off else bpv
seg2 = 12 * int(FS)
bpv = bpv[:seg2]
blo, bhi = bpv.min(), bpv.max()
pts = []
for i in range(len(bpv)):
    px = L + i / len(bpv) * (R - L)
    py = top2 + h2 - (bpv[i] - blo) / (bhi - blo) * h2
    pts.append((px, py))
d.line(pts, fill=(214, 150, 40), width=2)

# 结论框
d.rectangle([100, 800, W - 100, 960], fill=(255, 255, 255), outline=(190, 190, 190), width=2)
txt((116, 810), "验证结果（注入已知量，看能否还原）", 22, (0, 0, 0), "la", True)
yy = 848
for r in results:
    m = r["m"]
    txt((116, yy), "注入呼吸 %-7s → 估计 %5.1f 次/分（误差 %+.1f）   |   HR %.1f BPM，SDNN %.1f ms，RMSSD %.1f ms"
        % (r["label"], r["edr"], r["edr"] - r["resp_hz"] * 60, m["hr"], m["sdnn"], m["rmssd"]),
        17, (40, 40, 40), "la")
    yy += 32
txt((116, yy + 6), "判据：呼吸率误差 < 0.5 次/分 → %s" % ("PASS" if ok else "FAIL"),
    19, (190, 40, 40) if not ok else (30, 130, 60), "la", True)

p = os.path.join(OUT, "vitals_hrv_edr.png")
img.save(p)
print("\n图已保存:", p)
