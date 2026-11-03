#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""host_ecg.py —— 把外部样本灌进硬件滤波链（v5 + 精确时基）

架构变化
--------
v4 及以前：真实信号只能「XADC → Python 读 DRP → 软件滤波」，自己写的
           ecg_filt.v / PT 从未处理过真实数据，属于两个平行世界。

v5（本版）：0x10.bit3 = 1 → 滤波链输入改为 0x00 的低 12 位（有符号样本）
           → Python 写一个样本，就等于把它推进硬件链
           → 真实信号第一次经过自己写的 RTL 滤波器

时基（本版新增）
----------------
用 ecg_timebase.py 的 perf_counter 忙等，把采样率误差从 3.3% 压到 <0.3%，
否则 50 Hz 会被看成 51.65 Hz，硬件陷波（带宽 ±1.9 Hz）就形同虚设。

两个部分
--------
[A] 自测：Python 合成 50 Hz 正弦 → 硬件链
    干净实验（单一频率、无 R 波、不饱和）→ **用这一段判抑制比**
[B] 真实信号：XADC VP/VN → 硬件链
    ⚠ 只作「通路已打通」证据，不用它判抑制比（真实信号弱 + R 波频谱泄漏）

用法
----
    sudo -s
    python3 /boot/host_ecg.py
"""
import time

import numpy as np
from pynq import Overlay, MMIO

from ecg_timebase import FS_DEFAULT, sample_xadc, push_samples, format_stats

ECG_BASE  = 0x43C00000
XADC_BASE = 0x43C10000

REG_SAMPLE = 0x00      # 主机模式下 = 样本（低 12 位有符号）
REG_WADDR  = 0x04
REG_WDATA  = 0x0C
REG_CTL    = 0x10
REG_VER    = 0x14

BIT_BUF  = 1 << 0
BIT_PT   = 1 << 1
BIT_INJ  = 1 << 2
BIT_HOST = 1 << 3      # v5：主机样本模式

DEPTH = 1024
VERSION_EXPECT = 0xEC600005
BITSTREAM = "/boot/ecg_bd.bit"


def to_signed32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= 0x80000000 else v


def read_buffer(m):
    a = np.zeros(DEPTH, dtype=np.int32)
    for i in range(DEPTH):
        m.write(REG_WADDR, i)
        a[i] = to_signed32(m.read(REG_WDATA))
    return a


def amp_at(xs, f, fs=FS_DEFAULT):
    """单频幅度（正交相关，返回峰值幅度）"""
    x = np.asarray(xs, dtype=np.float64)
    x = x - x.mean()
    n = len(x)
    t = np.arange(n)
    c = np.sum(x * np.cos(2 * np.pi * f * t / fs))
    s = np.sum(x * np.sin(2 * np.pi * f * t / fs))
    return 2.0 * np.hypot(c, s) / n


def main():
    print("=" * 68)
    print("主机样本通道验证（v5 + 精确时基）")
    print("=" * 68)

    Overlay(BITSTREAM)
    time.sleep(1.0)
    m = MMIO(ECG_BASE, 0x1000)
    xadc = MMIO(XADC_BASE, 0x1000)

    ver = m.read(REG_VER)
    print("\n[1] 版本号 = 0x%08X" % ver)
    if ver != VERSION_EXPECT:
        print("    !! 期望 0x%08X，加载的不是 v5" % VERSION_EXPECT)
        return
    print("    OK：含主机样本通道")

    # ==================== A. 合成 50Hz 自测 ====================
    print("\n" + "-" * 68)
    print("[A] 自测：Python 合成 50 Hz 正弦 → 硬件链（判抑制比就看这一段）")
    print("-" * 68)

    N = 2048
    t = np.arange(N) / FS_DEFAULT
    sine = np.round(600.0 * np.sin(2 * np.pi * 50.0 * t)).astype(int)
    print("    %d 点 @%.0fHz，幅度 600 LSB，频率 50Hz" % (N, FS_DEFAULT))

    # A1：缓冲存原始
    m.write(REG_CTL, BIT_HOST)
    el = push_samples(m, REG_SAMPLE, sine)
    raw = read_buffer(m)
    a_raw = amp_at(raw, 50.0)
    print("    A1 缓冲=原始  ：50Hz = %6.1f LSB，峰值 = %4d，推送用时 %.3fs（%.0fHz）"
          % (a_raw, np.max(np.abs(raw)), el, N / el))

    # A2：缓冲存滤波后
    m.write(REG_CTL, BIT_HOST | BIT_BUF)
    el = push_samples(m, REG_SAMPLE, sine)
    flt = read_buffer(m)
    a_flt = amp_at(flt, 50.0)
    print("    A2 缓冲=滤波后：50Hz = %6.2f LSB，峰值 = %4d"
          % (a_flt, np.max(np.abs(flt))))

    if a_raw > 50:
        db = 20 * np.log10(max(a_flt, 1e-9) / a_raw)
        print("\n    [A3] 主机通道 + 硬件陷波：%.1f → %.2f LSB = %.1f dB  %s"
              % (a_raw, a_flt, db, "PASS ✓" if db <= -20 else "FAIL"))
        print("         （判据 优于 -20 dB；v4 上干净测得 -52.95 dB）")
    else:
        print("\n    [A3] !! 原始段只有 %.1f LSB，主机通道可能没生效" % a_raw)

    # ==================== B. 真实信号 ====================
    print("\n" + "-" * 68)
    print("[B] 真实信号：XADC VP/VN → 硬件链")
    print("-" * 68)

    N2 = 2048
    print("    精确采集 %d 个 XADC 样本（约 %.1f 秒）..." % (N2, N2 / FS_DEFAULT))
    real, st = sample_xadc(xadc, N2, FS_DEFAULT)
    print("    " + format_stats("XADC", st))
    print("    样本：min=%d max=%d mean=%.1f" % (real.min(), real.max(), real.mean()))

    m.write(REG_CTL, BIT_HOST)
    push_samples(m, REG_SAMPLE, real)
    r_raw = read_buffer(m)

    m.write(REG_CTL, BIT_HOST | BIT_BUF)
    push_samples(m, REG_SAMPLE, real)
    r_flt = read_buffer(m)

    print("\n    [B1] 缓冲=原始  ：峰值 %5d，p2p %5d，50Hz %6.1f LSB"
          % (np.max(np.abs(r_raw)), np.ptp(r_raw), amp_at(r_raw, 50.0)))
    print("    [B2] 缓冲=滤波后：峰值 %5d，p2p %5d，50Hz %6.1f LSB"
          % (np.max(np.abs(r_flt)), np.ptp(r_flt), amp_at(r_flt, 50.0)))

    print("\n    ⚠ 真实信号段只作「通路已打通」的证据：")
    print("      心电幅度低于噪声，且 R 波频谱会泄漏到 50Hz 附近。")
    print("      抑制比请看 A 段。")

    m.write(REG_CTL, 0)
    print("\n已恢复默认（0x10 = 0，DDS 波形、无注入）")
    print("=" * 68)


if __name__ == "__main__":
    main()
