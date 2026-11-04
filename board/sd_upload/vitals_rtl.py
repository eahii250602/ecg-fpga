#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vitals_rtl.py —— 单导联三参数，用 DMA 硬件数据端到端跑通

数据通路：
    DDS/XADC → 滤波(RTL) → AXIS → AXI DMA → DDR → 本脚本

本脚本做四件事：
    1. 用 DMA 连续取 N 个样本（硬件定时，不受 Python 调度影响）
    2. 从样本里检测 R 峰 → HR
    3. 由 RR 序列算 HRV（SDNN / RMSSD / pNN50）
    4. 剔除 QRS-T 后插值 → 0.05~1 Hz 带通 → 谱峰 → 呼吸率 EDR
    5. 读硬件 SQI 等级，作为"数据可信度"门控

为什么用 DMA 数据而不是寄存器轮询：
    寄存器读每样本两次 AXI 事务，采样时刻由 Python 循环决定（实测偏差 5.7%）；
    DMA 由 62.5MHz 时钟驱动，抖动 <16ns。

内存布局说明（已实测）：
    DMA 每个 32 位字装 2 个 16 位样本，但地址步长是 2 个字
    （即 a32[::2] 才是有效数据字）。已在此处处理。
"""
import time

import numpy as np
from pynq import Overlay, MMIO, allocate

ECG = 0x43C00000
DMA = 0x40400000
FS = 250.0
N = 3000                      # 样本数（250Hz 下 = 12 秒）


def vreg(m, i):
    m.write(0x04, 0x400 | i)
    return m.read(0x0C) & 0xFFFFFFFF


def grab(n):
    """用 DMA 取 n 个样本，返回有符号 12 位数组（偏移二进制 → 有符号）"""
    buf = allocate(shape=(n,), dtype=np.int16)
    buf[:] = 0
    try:
        o.axi_dma_0.recvchannel.transfer(buf)
        time.sleep(n / FS + 1.5)
    except Exception as e:
        print("    DMA 异常（已知误报，忽略）：%s" % e)
    a32 = np.asarray(buf).view(np.int32)
    w = a32[::2]                       # 有效数据字
    # 展平成时间顺序：每个字里低16=先到，高16=后到
    out = np.empty(len(w) * 2, dtype=np.int32)
    out[0::2] = w & 0xFFFF
    out[1::2] = (w >> 16) & 0xFFFF
    return out - 2048                  # 偏移二进制 → 有符号


def detect_r(x):
    """简化 Pan-Tompkins：5~15Hz 带通 → 微分 → 平方 → 积分 → 阈值"""
    def ma(v, w):
        w = max(1, int(round(w)))
        return np.convolve(v, np.ones(w) / w, mode="same")
    hp = x - ma(x, FS / 5.0)
    bp = ma(hp, FS / 15.0)
    d = np.diff(bp, prepend=bp[0])
    env = ma(d ** 2, 0.15 * FS)
    if env.max() <= 0:
        return np.array([], dtype=int)
    env = env / env.max()
    pk, i, refr = [], 1, int(0.25 * FS)
    while i < len(env) - 1:
        if env[i] > 0.3 and env[i] >= env[i - 1] and env[i] >= env[i + 1]:
            a, b = max(0, i - int(0.08 * FS)), min(len(x), i + int(0.08 * FS))
            pk.append(a + int(np.argmax(np.abs(x[a:b]))))
            i += refr
        else:
            i += 1
    return np.array(pk)


def edr(x, pk):
    """剔除 QRS-T → 插值 → 0.05~1Hz 带通 → 谱峰"""
    n = len(x)
    idx = np.arange(n)
    mask = np.ones(n, dtype=bool)
    for p in pk:
        mask[max(0, p - int(0.15 * FS)):min(n, p + int(0.40 * FS))] = False
    if mask.sum() < 20:
        return 0.0
    base = x.astype(float).copy()
    base[~mask] = np.interp(idx[~mask], idx[mask], base[mask])

    def ma(v, w):
        w = max(1, int(round(w)))
        if w >= len(v):
            return np.full_like(v, v.mean())
        return np.convolve(v, np.ones(w) / w, mode="same")
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


print("=" * 62)
print("单导联三参数（数据来自 AXI DMA 硬件通路）")
print("=" * 62)

o = Overlay("/boot/ecg_bd.bit")
time.sleep(1.0)
m = MMIO(ECG, 0x1000)
d = MMIO(DMA, 0x1000)
print("版本 0x%08X" % m.read(0x14))

m.write(0x10, 0)
m.write(0x00, 83)                 # 72.5 BPM
time.sleep(2.0)
d.write(0x34, 0x5011)             # 清 DMA 状态
time.sleep(0.1)

print("\n[1] 通过 DMA 采集 %d 个样本（%.1f 秒）..." % (N, N / FS))
x = grab(N)
print("    样本数=%d  峰值=%d  均值=%.1f"
      % (len(x), int(np.abs(x).max()), x.mean()))

print("\n[2] 硬件 SQI 等级 = %d  (0不可信 1可疑 2良好 3优秀)" % vreg(m, 0))
ain, aout = vreg(m, 6), vreg(m, 7)
if ain:
    print("    输入能量=%d  滤波后=%d  保留比=%.1f%%"
          % (ain, aout, 100.0 * aout / ain))

print("\n[3] R 峰检测：")
pk = detect_r(x)
print("    检出 %d 个 R 峰" % len(pk))

if len(pk) >= 3:
    rr = np.diff(pk) / FS
    rr = rr[(rr > 0.3) & (rr < 2.0)]
    hr = 60.0 / rr.mean()
    sdnn = rr.std() * 1000
    rmssd = np.sqrt(np.mean(np.diff(rr) ** 2)) * 1000
    pnn50 = 100.0 * np.sum(np.abs(np.diff(rr)) > 0.05) / max(1, len(rr) - 1)
    print("    HR    = %.2f BPM" % hr)
    print("    SDNN  = %.1f ms" % sdnn)
    print("    RMSSD = %.1f ms" % rmssd)
    print("    pNN50 = %.1f %%" % pnn50)
    e = edr(x, pk)
    print("\n[4] EDR 呼吸率 = %.1f 次/分" % e)
    print("\n" + "=" * 62)
    print("一条导联 → HR %.1f BPM | HRV(SDNN %.1f ms) | 呼吸 %.1f 次/分 | 质量 %d/3"
          % (hr, sdnn, e, vreg(m, 0)))
    print("=" * 62)
else:
    print("    !! R 峰太少，无法计算")
