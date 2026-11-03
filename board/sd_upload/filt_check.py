#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""filt_check.py —— D4/D5 滤波链上板实测（v2，2026-11-04 修正测量方法）

v1 的问题（2026-11-03 实测发现）：
    抑制比测出 -3.4 dB（应优于 -50 dB）。根因不是滤波器，而是**测试设计缺陷**：
    FTW=83 时心电 R 波峰值已达 2047（12 位正极限），再叠加 600 LSB 的 50Hz 注入
    → 和值 2647 被 12 位饱和削顶 → 正弦被削掉正半周，不再是纯正弦；
    同时 R 波的强频谱泄漏到 50Hz 附近 → 把真实抑制比彻底淹没。

v2 的修法（分两阶段测）：
    阶段 A（FTW=0，无心电）：信号 = 常数 + 600·sin(50Hz)，不饱和、无泄漏
        → 用这一阶段测抑制比，结果干净
    阶段 B（FTW=83，有心电）：测心电保真度与 PT 检出
        → 不用这一阶段测抑制比

寄存器（基址 0x43C00000）：
  0x00 W FTW（83 → 72.5 BPM；0 → 停在 ROM[0]，无 R 波）
  0x04 W 波形读地址（0~1023）   0x08 R 旧检测器 RR
  0x0C R 波形数据（32 位有符号） 0x10 R/W 滤波控制
        = [23:8]注入幅度 | bit2注入 | bit1 PT源 | bit0 缓冲源
  0x14 R 版本号  0x18 R PT 的 RR  0x1C R PT 检测次数

用法（板上）：
    sudo -s
    python3 /boot/filt_check.py
"""
import time

import numpy as np
from pynq import Overlay, MMIO

BASE        = 0x43C00000
REG_FTW     = 0x00
REG_WADDR   = 0x04
REG_WDATA   = 0x0C
REG_CTL     = 0x10
REG_VERSION = 0x14
REG_PT_RR   = 0x18
REG_PT_CNT  = 0x1C

FTW_72    = 83
NOISE_AMP = 600
WAVE_DEPTH = 1024
FS = 250.0
F_NOISE = 50.0
WAIT = 5.0                      # > 1024/250 = 4.096 s，保证缓冲整圈刷新

BIT_BUF = 1 << 0
BIT_PT  = 1 << 1
BIT_INJ = 1 << 2

BITSTREAM = "/boot/ecg_bd.bit"  # ★必须用 /boot 下这份（/home/xilinx 下是旧版 v2）
VERSION_EXPECT = 0xEC600005


def to_signed32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= 0x80000000 else v


def capture(mmio):
    wave = np.zeros(WAVE_DEPTH, dtype=np.int32)
    for i in range(WAVE_DEPTH):
        mmio.write(REG_WADDR, i)
        wave[i] = to_signed32(mmio.read(REG_WDATA))
    return wave


def amp_at(xs, f):
    """单频幅度（正交相关，返回峰值幅度）"""
    x = np.asarray(xs, dtype=np.float64)
    x = x - x.mean()
    n = len(x)
    t = np.arange(n)
    c = np.sum(x * np.cos(2 * np.pi * f * t / FS))
    s = np.sum(x * np.sin(2 * np.pi * f * t / FS))
    return 2.0 * np.hypot(c, s) / n


def main():
    print("=" * 64)
    print("D4/D5 滤波链上板实测 v2（分两阶段）")
    print("=" * 64)

    Overlay(BITSTREAM)
    time.sleep(1.0)                      # ★等 PL 复位释放，否则寄存器写入会丢
    mmio = MMIO(BASE, 0x1000)

    ver = mmio.read(REG_VERSION)
    print("\n[1] 版本号 = 0x%08X" % ver)
    if ver != VERSION_EXPECT:
        print("    !! 期望 0x%08X —— 加载的不是本设计的比特流" % VERSION_EXPECT)
        print("    !! 检查路径：%s" % BITSTREAM)
        return
    print("    OK：含滤波链 + 50Hz 注入器")

    # ================= 阶段 A：测抑制比（FTW=0，无心电） =================
    print("\n" + "-" * 64)
    print("阶段 A：测 50Hz 抑制比（FTW=0，无 R 波，避免饱和与泄漏）")
    print("-" * 64)

    mmio.write(REG_FTW, 0)
    time.sleep(0.2)

    ctl_raw = (NOISE_AMP << 8) | BIT_INJ          # 注入开、缓冲=原始
    mmio.write(REG_CTL, ctl_raw)
    time.sleep(WAIT)
    noisy = capture(mmio)
    a_raw = amp_at(noisy, F_NOISE)

    ctl_flt = ctl_raw | BIT_BUF                    # 注入开、缓冲=滤波后
    mmio.write(REG_CTL, ctl_flt)
    time.sleep(WAIT)
    filt = capture(mmio)
    a_flt = amp_at(filt, F_NOISE)

    print("\n[3] 缓冲存【原始】：50Hz 幅度=%.1f LSB，峰值=%d，均值=%.1f"
          % (a_raw, np.max(np.abs(noisy)), noisy.mean()))
    print("[4] 缓冲存【滤波后】：50Hz 幅度=%.2f LSB，峰值=%d，均值=%.2f"
          % (a_flt, np.max(np.abs(filt)), filt.mean()))

    print("\n[5] 实测抑制比")
    if a_raw < 100:
        print("    !! 原始段只有 %.1f LSB，注入可能没生效" % a_raw)
    elif a_flt < 0.1:
        print("    原始 %.1f -> 滤波后 %.3f LSB（已到量化下限）" % (a_raw, a_flt))
        print("    → 抑制优于 %.0f dB" % (20 * np.log10(0.5 / a_raw)))
    else:
        db = 20 * np.log10(a_flt / a_raw)
        print("    原始 %.1f LSB -> 滤波后 %.2f LSB = %.2f dB" % (a_raw, a_flt, db))
        print("    判定：%s（判据 优于 -20 dB）" % ("PASS ✓" if db <= -20 else "FAIL"))

    # ================= 阶段 B：保真 + PT（FTW=83，有心电） =================
    print("\n" + "-" * 64)
    print("阶段 B：心电保真 + PT 检出（FTW=83）")
    print("-" * 64)

    mmio.write(REG_CTL, 0)                 # 关注入、全走原始
    mmio.write(REG_FTW, FTW_72)
    time.sleep(WAIT)
    clean = capture(mmio)

    mmio.write(REG_CTL, BIT_BUF)           # 缓冲=滤波后、无注入
    time.sleep(WAIT)
    clean_f = capture(mmio)

    pk0 = float(np.max(np.abs(clean)))
    pk1 = float(np.max(np.abs(clean_f)))
    print("\n[6] 心电保真：原始峰值 %.0f → 滤波后峰值 %.0f（%.0f%%）"
          % (pk0, pk1, 100.0 * pk1 / max(pk0, 1.0)))

    print("\n[7] PT 检测（PT 输入切到滤波后）")
    mmio.write(REG_CTL, BIT_BUF | BIT_PT)
    time.sleep(0.5)
    d0 = mmio.read(REG_PT_CNT)
    time.sleep(8.0)
    d1 = mmio.read(REG_PT_CNT)
    n = (d1 - d0) & 0xFFFFFFFF
    print("    8 秒内检测 %d 次 → %.1f BPM（72.5 BPM 期望约 9.7 次）"
          % (n, n * 60.0 / 8.0))
    print("    PT 的 RR = %d 个采样点（期望约 207）" % mmio.read(REG_PT_RR))

    mmio.write(REG_CTL, 0)
    print("\n已恢复默认（0x10 = 0）")
    print("=" * 64)


if __name__ == "__main__":
    main()
