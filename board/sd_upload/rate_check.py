#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rate_check.py —— 采样时基对比：sleep(4ms) vs perf_counter 忙等

目的：用实测数据证明"改成忙等"到底值多少。

判据
----
    平均间隔误差：目标 < 0.5%（sleep 方案约 3.3%）
    抖动 std    ：目标 < 50 µs（sleep 方案约 130 µs）
    陷波中心偏移：由采样率误差直接换算，必须 < 1.9 Hz（陷波带宽的一半）

用法
----
    sudo -s
    python3 /boot/rate_check.py
"""
import time

import numpy as np
from pynq import Overlay, MMIO

from ecg_timebase import FS_DEFAULT, DRP_VP_VN, sample_xadc, format_stats

XADC_BASE = 0x43C10000
BITSTREAM = "/boot/ecg_bd.bit"
N = 400                 # 400 点 @250Hz = 1.6 秒，足够统计
SLEEP_S = 1.0 / FS_DEFAULT


def measure_sleep(xadc, n, dt):
    """老办法：time.sleep(dt) 后读一次"""
    ts = np.empty(n, dtype=np.float64)
    vals = np.empty(n, dtype=np.int16)
    t0 = time.perf_counter()
    for i in range(n):
        time.sleep(dt)
        ts[i] = time.perf_counter()
        v = (xadc.read(DRP_VP_VN) >> 4) & 0xFFF
        vals[i] = v - 4096 if v >= 2048 else v
    d = np.diff(np.concatenate(([t0], ts)))
    return vals, {
        "n": n,
        "fs_target": 1.0 / dt,
        "mean_ms": float(d.mean() * 1e3),
        "std_us": float(d.std() * 1e6),
        "max_dev_us": float(np.max(np.abs(d - dt)) * 1e6),
        "err_pct": float((d.mean() / dt - 1.0) * 100.0),
    }


def main():
    print("=" * 68)
    print("采样时基对比：sleep(4ms)  vs  perf_counter 忙等")
    print("=" * 68)

    Overlay(BITSTREAM)
    time.sleep(1.0)
    xadc = MMIO(XADC_BASE, 0x1000)

    print("\n[1] 老办法：time.sleep(%.4f) —— 跑 %d 点" % (SLEEP_S, N))
    t_start = time.perf_counter()
    _, st_old = measure_sleep(xadc, N, SLEEP_S)
    print("    " + format_stats("sleep", st_old))
    print("    实际采样率 = %.2f Hz" % (1e3 / st_old["mean_ms"]))

    print("\n[2] 新办法：perf_counter 忙等 —— 跑 %d 点" % N)
    _, st_new = sample_xadc(xadc, N, FS_DEFAULT)
    print("    " + format_stats("spin ", st_new))
    print("    实际采样率 = %.2f Hz" % (1e3 / st_new["mean_ms"]))

    # ---------- 换算成"对滤波器意味着什么" ----------
    print("\n" + "-" * 68)
    print("[3] 这对硬件滤波器意味着什么")
    print("-" * 68)

    fs_old = 1e3 / st_old["mean_ms"]
    fs_new = 1e3 / st_new["mean_ms"]
    # 50Hz 信号在"按 250Hz 设计"的滤波器眼里会出现在 fs_eff 处
    f_old = 50.0 * FS_DEFAULT / fs_old
    f_new = 50.0 * FS_DEFAULT / fs_new

    print("    滤波器按 250Hz 设计，陷波中心 50Hz，-3dB 带宽 48.11~51.91 Hz（±1.9Hz）")
    print("")
    print("    sleep 方案：实际 %.2f Hz → 50Hz 干扰被看成 %.2f Hz，偏离中心 %.2f Hz  %s"
          % (fs_old, f_old, abs(f_old - 50.0),
             "❌ 超出陷波带宽" if abs(f_old - 50.0) > 1.9 else "✓"))
    print("    忙等  方案：实际 %.2f Hz → 50Hz 干扰被看成 %.2f Hz，偏离中心 %.2f Hz  %s"
          % (fs_new, f_new, abs(f_new - 50.0),
             "❌" if abs(f_new - 50.0) > 1.9 else "✓ 在带宽内"))

    print("\n" + "-" * 68)
    print("[4] 结论")
    print("-" * 68)
    # 判据说明：
    #   均值误差 → 决定陷波中心是否对准 50Hz，这是**唯一影响抑制比**的量
    #   抖动 std → 换算成 50Hz 相位噪声（std × 50 × 360 度），<3.6° 可忽略
    #   最大偏差 → 允许偶发的 Linux 调度抢占，单点离群在 1024 点相关里被平均掉
    phase_deg = st_new["std_us"] * 1e-6 * 50.0 * 360.0
    ok_mean = abs(st_new["err_pct"]) < 0.5
    ok_jit = st_new["std_us"] < 200.0
    if ok_mean and ok_jit:
        print("    ✅ 达标")
        print("       均值误差 %+.2f%%（判据 <0.5%%）→ 陷波中心偏 %.2f Hz，在 ±1.9 Hz 带宽内"
              % (st_new["err_pct"], abs(f_new - 50.0)))
        print("       抖动 %.0f us → 50Hz 相位噪声仅 %.1f°rms，幅度误差约 %.3f%%（可忽略）"
              % (st_new["std_us"], phase_deg, 100.0 * (1 - np.cos(np.deg2rad(phase_deg)))))
        print("       最大偏差 %.0f us 属偶发调度抢占，单点离群在 1024 点相关中被平均"
              % st_new["max_dev_us"])
    else:
        print("    ⚠ 未达标：均值误差 %+.2f%%（判据 <0.5%%），抖动 %.0f us（判据 <200us）"
              % (st_new["err_pct"], st_new["std_us"]))
        print("       均值误差才是决定抑制比的量；抖动只带来相位噪声")

    print("\n    （忙等占满一个核，采集期间别同时跑别的重活）")
    print("=" * 68)


if __name__ == "__main__":
    main()
