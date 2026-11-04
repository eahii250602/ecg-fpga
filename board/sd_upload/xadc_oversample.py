#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xadc_oversample.py —— XADC 过采样验证（零 RTL 改动）

要验证的命题
------------
"我们每秒浪费了 3999 次 XADC 转换。把它们用起来，等于免费获得
 约 30 dB 的 SNR 提升 + 一道 50Hz 梳状抑制。"

方法：同一次运行里采两段，直接对比
    段 A（现状）：每 4 ms 读 1 次 XADC
    段 B（过采样）：每 4 ms 内连续读 OS 次并取平均
    指标：5~15 Hz 频段幅度 / 噪声本底（1~4 Hz 与 20~40 Hz）

为什么这个对比是公平的
    两段用的是同一个电极、同一段时间、同一个 XADC，
    唯一差别是"每次输出平均了多少次转换"。

硬件操作
    1. 打开主机样本模式（0x10 bit3=1），XADC 的样本由本脚本写入 0x00
    2. 采样时刻用 perf_counter 忙等保证 250.00 Hz
"""
import sys
import time

import numpy as np
from pynq import Overlay, MMIO

ECG = 0x43C00000
XADC = 0x43C10000
DRP_VP_VN = 0x20C
FS = 250.0
DUR = 8.0          # 每段时长（秒）
OS_LIST = [1, 800]  # 对比的过采样倍数


def band_amp(x, fs, lo, hi):
    """返回某频段的幅度（用 FFT 峰值的均方根）"""
    n = len(x)
    if n < 64:
        return 0.0
    sp = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(n))) / n * 2
    fr = np.fft.rfftfreq(n, 1 / fs)
    sel = (fr >= lo) & (fr <= hi)
    return float(np.sqrt(np.mean(sp[sel] ** 2)))


def capture(ecg, xadc, dur, os_n):
    """采集 dur 秒，每 4ms 输出一个样本；os_n = 每次输出平均的转换数"""
    n_out = int(dur * FS)
    out = np.empty(n_out, dtype=np.int16)
    t_next = time.perf_counter()
    for i in range(n_out):
        acc = 0
        if os_n == 1:
            acc = (xadc.read(DRP_VP_VN) >> 4) & 0xFFF
        else:
            for _ in range(os_n):
                acc += (xadc.read(DRP_VP_VN) >> 4) & 0xFFF
            acc //= os_n
        ecg.write(0x00, acc)          # 推到硬件链（主机样本模式）
        out[i] = acc
        # 忙等到下一个 4ms 边界（不用 sleep，避免 jitter）
        t_next += 1.0 / FS
        while time.perf_counter() < t_next:
            pass
    return out.astype(np.int32)


def main():
    print("=" * 68)
    print("XADC 过采样验证")
    print("=" * 68)

    o = Overlay("/boot/ecg_bd.bit")
    time.sleep(1.0)
    ecg = MMIO(ECG, 0x1000)
    xadc = MMIO(XADC, 0x1000)
    print("版本 0x%08X" % ecg.read(0x14))

    # 主机样本模式（bit3），不注入（bit2=0），缓冲存原始（bit0=0）
    ecg.write(0x10, 0x8)
    time.sleep(0.3)

    results = {}
    for os_n in OS_LIST:
        print("\n[采集] 过采样倍数 OS=%d，%0.0f 秒 ..." % (os_n, DUR))
        x = capture(ecg, xadc, DUR, os_n)
        p2p = int(x.max() - x.min())
        sig = band_amp(x, FS, 5.0, 15.0)     # QRS 频段
        nlo = band_amp(x, FS, 1.0, 4.0)      # 低频干扰
        nhi = band_amp(x, FS, 20.0, 40.0)    # 肌电/高频
        noise = max(nlo, nhi)
        snr = sig / max(noise, 1e-9)
        results[os_n] = (p2p, sig, noise, snr)
        print("    p2p=%4d  5-15Hz幅度=%7.2f  噪声=%7.2f  SNR=%6.2f"
              % (p2p, sig, noise, snr))

    print("\n" + "=" * 68)
    print("对比结果")
    print("=" * 68)
    base = results[OS_LIST[0]][3]
    for os_n in OS_LIST:
        p2p, sig, noise, snr = results[os_n]
        gain = 20 * np.log10(snr / max(base, 1e-9)) if base > 0 else 0
        print("  OS=%-4d  p2p=%4d  SNR=%6.2f  相对提升=%+6.2f dB"
              % (os_n, p2p, snr, gain))

    best = max(OS_LIST, key=lambda k: results[k][3])
    b = results[best][3]
    if b / max(base, 1e-9) >= 1.5:
        print("\n  >>> 过采样有效（SNR 提升 %.1f 倍）" % (b / max(base, 1e-9)))
        print("  >>> 建议用 OS=%d 做后续采集" % best)
    else:
        print("\n  >>> 过采样未带来明显提升：说明限制因素不是随机噪声，")
        print("      而是 50Hz 工频或电极接触（这两者过采样救不了）")

    print("\n  判读提示：")
    print("    p2p < 10 码        → 几乎没信号（电极/接触问题）")
    print("    p2p 10~100 码      → 有信号但弱，过采样后可尝试分析")
    print("    p2p > 100 码       → 信号良好，可直接跑三参数")
    ecg.write(0x10, 0)


if __name__ == "__main__":
    sys.exit(main())
