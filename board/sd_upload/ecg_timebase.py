#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ecg_timebase.py —— 精确时间基（replace 粗粒度 sleep）

问题
----
`time.sleep(0.004)` 的粒度约 1 ms，实测平均 **4.13 ms**（误差 3.3%）：
    → 采样率 242 Hz 而不是 250 Hz
    → 陷波中心从 50 Hz 偏到 51.65 Hz，而陷波带宽只有 ±1.9 Hz
    → 抑制比从 -53 dB 掉到 -3 dB（这是 2026-11-03 那个结论的另一个隐患）

做法
----
用 `time.perf_counter()`（纳秒级单调时钟）**忙等到绝对时刻**再采样：
    deadline = t0 + (i+1)/fs
    while perf_counter() < deadline: pass
    sample = read()

关键细节
--------
**先等到时刻，再去读**。如果先读再等，读操作本身的耗时会累积成时间偏移；
先等后读，采样时刻 = 目标时刻 + 固定的读取延迟（常数偏移，不影响频率响应）。

预期效果
--------
    平均间隔误差：3.3%  →  < 0.3%
    抖动：        ±130 µs →  ±10 µs

代价
----
忙等会占满一个 CPU 核。250 Hz 下采样本身只占约 0.5% 的时间，
但 Python 循环判空会跑满——对短时采集（秒级）完全可接受。
"""
import time

import numpy as np

FS_DEFAULT = 250.0
DRP_VP_VN = 0x200 + 4 * 3          # XADC DRP：通道 3 = VP/VN


def _signed12(v):
    return v - 4096 if v >= 2048 else v


def sample_xadc(xadc, n, fs=FS_DEFAULT, warmup=0.05):
    """按 fs 精确采样 n 个点，返回 (样本数组, 统计字典)

    xadc : pynq.MMIO 实例（基址 0x43C10000）
    warmup : 开始前的准备时间（秒），让第一次等待不至于过冲
    """
    period = 1.0 / fs
    out = np.empty(n, dtype=np.int16)
    ts = np.empty(n, dtype=np.float64)

    t0 = time.perf_counter() + warmup
    pc = time.perf_counter

    for i in range(n):
        dl = t0 + (i + 1) * period
        while pc() < dl:
            pass
        ts[i] = pc()
        out[i] = _signed12((xadc.read(DRP_VP_VN) >> 4) & 0xFFF)

    d = np.diff(ts)
    stats = {
        "n": n,
        "fs_target": fs,
        "mean_ms": float(d.mean() * 1e3),
        "std_us": float(d.std() * 1e6),
        "max_dev_us": float(np.max(np.abs(d - period)) * 1e6),
        "err_pct": float((d.mean() * fs - 1.0) * 100.0),
    }
    return out, stats


def push_samples(m, reg_addr, samples, fs=FS_DEFAULT, warmup=0.05):
    """按 fs 精确把样本写入寄存器（主机样本模式用）

    m        : ECG IP 的 MMIO
    reg_addr : 写样本的寄存器偏移（主机模式下是 0x00）
    """
    period = 1.0 / fs
    t0 = time.perf_counter() + warmup
    pc = time.perf_counter

    for i, v in enumerate(samples):
        dl = t0 + (i + 1) * period
        while pc() < dl:
            pass
        m.write(reg_addr, int(v) & 0x0FFF)

    return time.perf_counter() - t0


def format_stats(tag, st):
    return ("%s: n=%d  mean=%.3f ms  std=%.1f us  最大偏差=%.1f us  误差=%+.2f%%"
            % (tag, st["n"], st["mean_ms"], st["std_us"],
               st["max_dev_us"], st["err_pct"]))
