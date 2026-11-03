# -*- coding: utf-8 -*-
"""验证：板上测到的 298 / 202 LSB 到底是「滤波没生效」还是「测量方法有泄漏」"""
import json
import os
import numpy as np

BASE = r"D:\ecg"
FS = 250.0
F0 = 50.0
DEPTH = 1024


def amp_at(xs, f, fs=FS):
    """与 filt_check.py 完全一致的测量函数"""
    x = np.asarray(xs, dtype=np.float64)
    x = x - x.mean()
    n = len(x)
    t = np.arange(n)
    c = np.sum(x * np.cos(2 * np.pi * f * t / fs))
    s = np.sum(x * np.sin(2 * np.pi * f * t / fs))
    return 2.0 * np.hypot(c, s) / n


# ---------- 1. 纯正弦：验证测量函数本身 ----------
for A in (600,):
    for ncyc, label in ((204.8, "非整数周期(1024点)"), (200.0, "整数周期(1000点)")):
        n = int(round(ncyc * FS / F0))
        t = np.arange(n)
        x = A * np.sin(2 * np.pi * F0 * t / FS + 0.7)
        print("[纯正弦 A=%d] %-18s n=%4d -> amp_at = %.1f LSB (应=%d)"
              % (A, label, n, amp_at(x, F0), A))

# ---------- 2. 心电 + 注入 ----------
rom = []
with open(os.path.join(BASE, "python", "ecg_256x12.mem")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("//"):
            rom.append(int(line, 16) if any(c in "abcdefABCDEF" for c in line) else int(line))
rom = np.array(rom, dtype=np.int64)
if rom.max() > 2047:                      # offset-binary
    rom = rom - 2048
print("\nROM: n=%d  min=%d max=%d" % (len(rom), rom.min(), rom.max()))

FTW = 83
step = (250000 * FTW) % (1 << 32)         # 每采样点相位增量
n = DEPTH + 400
ph = (np.arange(n, dtype=np.int64) * step) % (1 << 32)
ecg = rom[(ph >> 24).astype(int)]

t = np.arange(n)
inj = 600.0 * np.sin(2 * np.pi * F0 * t / FS + 0.0)
raw = ecg + inj

# ---------- 3. 定点滤波（Q2.14，两级 biquad） ----------
with open(os.path.join(BASE, "sim", "filt", "out", "filt_coef.json")) as f:
    co = json.load(f)


def get_coefs(name):
    """优先取定点系数；键名兼容多种写法"""
    for key in (name, name + "_q14", name + "_fixed"):
        if key in co:
            v = co[key]
            if isinstance(v, dict):
                for k2 in ("q14", "fixed", "b"):
                    if k2 in v:
                        return np.array(v[k2], dtype=np.int64)
            else:
                return np.array(v, dtype=np.int64)
    return None


print("coef.json 顶层键:", list(co.keys())[:10])

sections = []
for nm in ("notch50", "notch_50", "biquad1", "s1", "lowpass40", "lowpass_40", "biquad2", "s2"):
    c = get_coefs(nm)
    if c is not None and len(c) == 5:
        sections.append((nm, c))
print("找到的 biquad 段: %d" % len(sections))


def run_biquad(x, b, fs_note=""):
    """Direct Form I，Q2.14，四舍五入右移 14"""
    b0, b1, b2, a1, a2 = [int(v) for v in b]
    y = np.zeros(len(x), dtype=np.int64)
    x1 = x2 = y1 = y2 = 0
    for i in range(len(x)):
        acc = b0 * int(x[i]) + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        v = (acc + (1 << 13)) >> 14
        v = max(-2048, min(2047, v))
        x2, x1 = x1, int(x[i])
        y2, y1 = y1, v
        y[i] = v
    return y


if sections:
    y = raw.astype(np.int64)
    for nm, c in sections:
        y = run_biquad(y, c)
        print("  过 %-10s -> 峰值 %d" % (nm, np.max(np.abs(y))))
    filt = y
else:
    print("!! 没找到定点系数，跳过滤波")
    filt = None

# ---------- 4. 结论 ----------
print("\n" + "=" * 60)
print("板上实测： 原始 298.1 LSB   滤波后 202.38 LSB")
print("=" * 60)
w = slice(400, 400 + DEPTH)
a_raw_sim = amp_at(raw[w], F0)
print("仿真 原始段 amp_at(50Hz) = %.1f LSB" % a_raw_sim)
if filt is not None:
    a_flt_sim = amp_at(filt[w], F0)
    print("仿真 滤波段 amp_at(50Hz) = %.1f LSB" % a_flt_sim)
    print("仿真 抑制比 = %.1f dB" % (20 * np.log10(max(a_flt_sim, 1e-9) / max(a_raw_sim, 1e-9))))
    # 只含心电（无注入）的滤波输出，看它的 50Hz 泄漏有多少
    ecg_f = run_biquad(ecg.astype(np.int64), sections[0][1])
    for nm, c in sections[1:]:
        ecg_f = run_biquad(ecg_f, c)
    print("纯心电(无注入)滤波后 amp_at(50Hz) = %.1f LSB  <- 这就是「泄漏底」" % amp_at(ecg_f[w], F0))
