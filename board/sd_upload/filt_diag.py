#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""filt_diag.py —— D4/D5 滤波链诊断（5 组对照 + 原始数据落盘）

板上运行：
    cd /boot && python3 filt_diag.py

产出：/boot/filt_diag.txt —— 5 组、每组 1024 个采样点，全部明文。
把 SD 卡拿回电脑即可用 numpy 深入分析（FFT、波形形状、溢出检查）。

为什么要 5 组：板上测到"注入 600 只有 297"、"滤波后峰值还是 2047"，
两个现象互相矛盾，必须把【注入幅度】和【滤波器是否生效】分开验证。
A 组把心电关掉（FTW=0），缓冲里只剩纯 50Hz 正弦 —— 测到多少就是注入多少。
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

FTW_72  = 83
AMP     = 600
DEPTH   = 1024
FS      = 250.0
BIT_BUF = 1 << 0
BIT_PT  = 1 << 1
BIT_INJ = 1 << 2

CTL_INJ_RAW = (AMP << 8) | BIT_INJ          # 0x00025804
CTL_INJ_FLT = (AMP << 8) | BIT_INJ | BIT_BUF  # 0x00025805

CASES = [
    ("A_dc_inj_raw",   0,      CTL_INJ_RAW, "心电关(纯直流) + 注入600，缓冲存原始"),
    ("B_dc_inj_flt",   0,      CTL_INJ_FLT, "心电关(纯直流) + 注入600，缓冲存滤波后"),
    ("C_ecg_inj_raw",  FTW_72, CTL_INJ_RAW, "心电开 + 注入600，缓冲存原始"),
    ("D_ecg_inj_flt",  FTW_72, CTL_INJ_FLT, "心电开 + 注入600，缓冲存滤波后"),
    ("E_ecg_noinj_raw", FTW_72, 0,          "心电开 + 不注入（基线）"),
]


def to_signed32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= 0x80000000 else v


def capture(mmio):
    w = np.zeros(DEPTH, dtype=np.int32)
    for i in range(DEPTH):
        mmio.write(REG_WADDR, i)
        w[i] = to_signed32(mmio.read(REG_WDATA))
    return w


def amp_at(xs, f):
    x = np.asarray(xs, dtype=np.float64)
    x = x - x.mean()
    n = len(x)
    t = np.arange(n)
    c = np.sum(x * np.cos(2 * np.pi * f * t / FS))
    s = np.sum(x * np.sin(2 * np.pi * f * t / FS))
    return 2.0 * np.hypot(c, s) / n


def main():
    print("=" * 70)
    print("D4/D5 滤波链诊断：5 组对照")
    print("=" * 70)

    Overlay("/boot/ecg_bd.bit")
    mmio = MMIO(BASE, 0x1000)

    ver = mmio.read(REG_VERSION)
    print("版本号 = 0x%08X" % ver)
    if ver != 0xEC600004:
        print("!! 版本不对，停止")
        return

    results = []
    for name, ftw, ctl, desc in CASES:
        mmio.write(REG_FTW, ftw)
        mmio.write(REG_CTL, ctl)
        time.sleep(5.0)
        w = capture(mmio)
        results.append((name, ftw, ctl, desc, w))
        a50 = amp_at(w, 50.0)
        print("\n[%s] %s" % (name, desc))
        print("    ftw=%d  ctl=0x%08X" % (ftw, ctl))
        print("    范围=[%d, %d]  均值=%.1f  50Hz=%.2f LSB"
              % (w.min(), w.max(), w.mean(), a50))
        print("    前 16 点: %s" % (" ".join("%5d" % v for v in w[:16])))
        print("    点 300-315: %s" % (" ".join("%5d" % v for v in w[300:316])))

    # ---- 找最强频率（粗扫 5~120Hz）----
    print("\n" + "=" * 70)
    print("各组的最强频率（5~120Hz 粗扫，步长 0.5Hz）")
    print("=" * 70)
    for name, ftw, ctl, desc, w in results:
        best_f, best_a = 0.0, 0.0
        f = 5.0
        while f <= 120.0:
            a = amp_at(w, f)
            if a > best_a:
                best_a, best_f = a, f
            f += 0.5
        print("  %-16s 最强 %.1f Hz 幅度 %.1f LSB" % (name, best_f, best_a))

    # ---- 落盘 ----
    path = "/boot/filt_diag.txt"
    with open(path, "w") as f:
        f.write("# D4/D5 滤波链诊断数据  FS=250Hz  DEPTH=1024\n")
        f.write("# 格式: CASE <名字> <ftw> <ctl> <说明>\n#       后接 1024 行采样值\n")
        for name, ftw, ctl, desc, w in results:
            f.write("CASE %s %d %d %s\n" % (name, ftw, ctl, desc))
            for v in w:
                f.write("%d\n" % int(v))
    print("\n数据已写入 %s（5 组 × 1024 点）" % path)
    print("请把 SD 卡拿回电脑，我用 numpy 做完整分析")

    mmio.write(REG_CTL, 0)
    mmio.write(REG_FTW, FTW_72)
    print("已恢复默认")
    print("=" * 70)


if __name__ == "__main__":
    main()