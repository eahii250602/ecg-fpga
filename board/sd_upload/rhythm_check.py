#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rhythm_check.py —— 单导联三参数 + 心律失常筛查

与 vitals_rtl.py 的区别：
    1. 修正了缓冲区大小（DMA 内存步长 2×，需申请 2N）
    2. 增加了 T 波判别（能量不到中位数一半的峰丢弃）——与 RTL 里的修法同源
    3. 增加了临床判读规则，输出"一句结论"而不是一堆数字

判读规则及其依据：
    CV = SDNN / mean(RR)
        > 0.15 → 心律不齐
        健康人静息 CV 约 0.03~0.10
    pNN50 高 + RMSSD 高
        相邻 RR 剧烈跳变是房颤（AFib）的典型特征：
        房颤时 RR 绝对不规则，pNN50 常 > 50%
    单个 RR < 0.8 × 中位数
        提前出现的搏动 → 早搏（PAC/PVC）
"""
import time

import numpy as np
from pynq import Overlay, MMIO, allocate

ECG, DMA = 0x43C00000, 0x40400000
FS = 250.0
N = 3000


def vreg(m, i):
    m.write(0x04, 0x400 | i)
    return m.read(0x0C) & 0xFFFFFFFF


def grab(o, n):
    """DMA 取数。内存步长 2× → 申请 2n 个 int16"""
    buf = allocate(shape=(2 * n,), dtype=np.int16)
    buf[:] = 0
    try:
        o.axi_dma_0.recvchannel.transfer(buf)
        time.sleep(n / FS + 2.0)
    except Exception:
        pass
    a32 = np.asarray(buf).view(np.int32)
    w = a32[::2]
    out = np.empty(len(w) * 2, dtype=np.int32)
    out[0::2] = w & 0xFFFF
    out[1::2] = (w >> 16) & 0xFFFF
    return (out - 2048).astype(np.float64)


def envelope(x):
    def ma(v, k):
        k = max(1, int(round(k)))
        return np.convolve(v, np.ones(k) / k, mode="same")
    hp = x - ma(x, FS / 5.0)
    bp = ma(hp, FS / 15.0)
    d = np.diff(bp, prepend=bp[0])
    return ma(d ** 2, 0.15 * FS)


def detect_r(x, env):
    """包络阈值 + 幅度判别（剔除 T 波）+ 不应期"""
    if env.max() <= 0:
        return np.array([], dtype=int)
    e = env / env.max()
    cand = np.where((e[1:-1] > 0.3) & (e[1:-1] >= e[:-2]) & (e[1:-1] >= e[2:]))[0] + 1
    if len(cand) == 0:
        return np.array([], dtype=int)
    # T 波判别：能量不到候选峰值中位数一半的丢弃（与 RTL 的 spki>>1 同源）
    vals = e[cand]
    keep = cand[vals >= 0.5 * np.median(vals)]
    # 不应期
    pk, last = [], -10 ** 9
    refr = int(0.25 * FS)
    for p in keep:
        if p - last >= refr:
            a = max(0, p - int(0.08 * FS))
            b = min(len(x), p + int(0.08 * FS))
            pk.append(a + int(np.argmax(np.abs(x[a:b]))))
            last = p
    return np.array(pk)


def edr(x, pk):
    n = len(x)
    idx = np.arange(n)
    mask = np.ones(n, dtype=bool)
    for p in pk:
        mask[max(0, p - int(0.15 * FS)):min(n, p + int(0.40 * FS))] = False
    if mask.sum() < 20:
        return 0.0
    base = x.copy()
    base[~mask] = np.interp(idx[~mask], idx[mask], base[mask])

    def ma(v, k):
        k = max(1, int(round(k)))
        if k >= len(v):
            return np.full_like(v, v.mean())
        return np.convolve(v, np.ones(k) / k, mode="same")
    bp = base - ma(base, FS / 0.05)
    bp = ma(bp, FS / 1.0)
    e = int(FS * 2)
    bp = bp[e:-e]
    if len(bp) < 64:
        return 0.0
    sp = np.abs(np.fft.rfft(bp * np.hanning(len(bp))))
    fr = np.fft.rfftfreq(len(bp), 1 / FS)
    sel = (fr >= 0.08) & (fr <= 0.80)
    return float(fr[sel][np.argmax(sp[sel])] * 60.0)


def verdict(rr):
    """临床判读：返回 (结论, 依据)"""
    if len(rr) < 5:
        return "数据不足", "RR 间期少于 5 个"
    med = np.median(rr)
    cv = rr.std() / rr.mean()
    rmssd = np.sqrt(np.mean(np.diff(rr) ** 2))
    pnn50 = 100.0 * np.sum(np.abs(np.diff(rr)) > 0.05) / max(1, len(rr) - 1)
    short = np.sum(rr < 0.8 * med)

    if pnn50 > 50 and rmssd > 0.050:
        return "疑似房颤（RR 绝对不规则）", "pNN50=%.0f%% RMSSD=%.0fms" % (pnn50, rmssd * 1000)
    if short >= 1:
        return "检出早搏", "%d 个 RR 短于中位数的 80%%" % short
    if cv > 0.15:
        return "心律不齐", "CV=%.3f" % cv
    return "心律规整", "CV=%.3f pNN50=%.0f%%" % (cv, pnn50)


print("=" * 66)
print("单导联三参数 + 心律失常筛查")
print("=" * 66)

o = Overlay("/boot/ecg_bd.bit")
time.sleep(1.0)
m = MMIO(ECG, 0x1000)
d = MMIO(DMA, 0x1000)
print("版本 0x%08X" % m.read(0x14))

m.write(0x10, 0)
m.write(0x00, 83)
time.sleep(2.0)
d.write(0x34, 0x5011)
time.sleep(0.1)

print("\n[1] DMA 采集 %d 样本（%.0f 秒）..." % (N, N / FS))
x = grab(o, N)
print("    样本=%d 时长=%.1fs 峰值=%d" % (len(x), len(x) / FS, int(np.abs(x).max())))

sqi = vreg(m, 0)
print("\n[2] 硬件 SQI 等级 = %d/3" % sqi)

env = envelope(x)
pk = detect_r(x, env)
print("\n[3] R 峰检出 %d 个" % len(pk))

if len(pk) >= 6:
    rr = np.diff(pk) / FS
    rr = rr[(rr > 0.3) & (rr < 2.0)]
    hr = 60.0 / rr.mean()
    sdnn = rr.std() * 1000
    rmssd = np.sqrt(np.mean(np.diff(rr) ** 2)) * 1000
    pnn50 = 100.0 * np.sum(np.abs(np.diff(rr)) > 0.05) / max(1, len(rr) - 1)
    cv = rr.std() / rr.mean()
    edr_v = edr(x, pk)
    v, why = verdict(rr)

    print("    HR    = %.2f BPM" % hr)
    print("    SDNN  = %.1f ms   RMSSD = %.1f ms   pNN50 = %.1f%%" % (sdnn, rmssd, pnn50))
    print("    CV    = %.3f" % cv)
    print("\n[4] EDR 呼吸率 = %.1f 次/分" % edr_v)
    print("\n[5] 心律判读：%s   （依据：%s）" % (v, why))

    print("\n" + "=" * 66)
    print("HR %.1f BPM | SDNN %.1f ms | 呼吸 %.1f 次/分 | %s | 质量 %d/3"
          % (hr, sdnn, edr_v, v, sqi))
    print("=" * 66)
else:
    print("    !! R 峰太少")
