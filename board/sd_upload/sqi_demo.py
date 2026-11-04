#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sqi_demo.py —— 一屏展示 SQI 在两种输入条件下的对比

用途：生成技术文档 3.3 节的"SQI 对比"截图。跑一次，截一张即可。

设计要点
--------
1. 【单次 Overlay】整个演示在一个进程内完成。Overlay() 会重载比特流并复位
   全部硬件状态，跨进程读数据必然失效（本项目实测踩过三次）。

2. 【切换后等 2 秒】SQI 用的是泄漏积分器（时间常数 256 个采样 ≈ 1.02 秒），
   改变输入条件后必须等它收敛，否则读到的是过渡过程的值。

3. 【波形读取用寄存器通路】不用 DMA —— DMA 的地址步长是 2 倍，会写出缓冲区
   边界并踩坏 DDR（已造成过一次整机冻结）。演示代码不能用会挂死的通路。

4. 【两屏停住不刷新】目的是一张截图能同时容纳两种状态。
"""
import os
import sys
import time

import numpy as np
from pynq import Overlay, MMIO

ECG = 0x43C00000
FS = 250.0
N = 600                     # 每屏采样点（2.4 秒）
BLOCKS = " ▁▂▃▄▅▆▇█"
G, Y, R, D = "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def term_size():
    try:
        s = os.get_terminal_size()
        return max(60, min(s.columns - 2, 150)), 9
    except Exception:
        return 100, 9


COLS, ROWS = term_size()


def vreg(m, i):
    m.write(0x04, 0x400 | i)
    return m.read(0x0C) & 0xFFFFFFFF


def grab(m, n, addr0=0):
    """从波形缓冲顺序读 n 点（寄存器通路）"""
    out = np.empty(n, dtype=np.int16)
    a = addr0
    for i in range(n):
        m.write(0x04, a & 0x3FF)
        out[i] = (m.read(0x0C) & 0xFFFF) - 2048
        a += 1
    return out


def render(x, color):
    """与 term_monitor 同一套：峰值保持降采样 + 中位数居中 + 开方压缩 + 折线绘制"""
    seg = x.astype(np.float64)
    base0 = float(np.median(seg))
    step = max(1, len(seg) // COLS)
    n = len(seg) // step
    seg = seg[:n * step].reshape(n, step)
    pick = np.argmax(np.abs(seg - base0), axis=1)
    seg = seg[np.arange(n), pick][-COLS:]

    base = float(np.median(seg))
    amp = max(1.0, float(np.abs(seg - base).max()))
    dev = (seg - base) / amp
    h = np.sqrt(np.abs(dev)) * np.sign(dev)
    h = (h + 1.0) * 0.5 * (ROWS - 1)

    lines = []
    for r in range(ROWS - 1, -1, -1):
        buf = []
        for i, hv in enumerate(h):
            hp = h[i - 1] if i > 0 else hv
            lo, hi = (hv, hp) if hv <= hp else (hp, hv)
            at_v = int(round(hv)) == r
            if at_v and abs(hv - hp) < 0.6:
                buf.append(color + "━" + D)
            elif at_v:
                buf.append(color + "█" + D)
            elif lo <= r + 0.5 <= hi:
                buf.append(color + "┃" + D)
            else:
                buf.append(" ")
        lines.append("".join(buf))
    return lines, int(amp)


def panel(m, title, ctl, color, tag):
    """切换条件 → 等待收敛 → 采集 → 返回若干行文本"""
    m.write(0x10, ctl)
    time.sleep(2.2)                       # 等 SQI 泄漏积分器收敛
    sqi = vreg(m, 0)
    ain, aout = vreg(m, 6), vreg(m, 7)
    keep = (100.0 * aout / ain) if ain else 0.0
    x = grab(m, N)
    body, amp = render(x, color)
    q = ["不可信", "可疑", "良好", "优秀"][sqi] if 0 <= sqi <= 3 else "?"
    out = []
    out.append("%s┏━ %s ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s"
               % (color, title, D))
    out.append("%s┃ SQI 等级 = %d（%s）   输入能量 %-9d  滤波后 %-9d  能量保留 %5.1f%%%s"
               % (color, sqi, q, ain, aout, keep, D))
    out.append("%s┃ 峰值 %d%s" % (color, amp, D))
    out += body
    out.append("%s┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s"
               % (color, D))
    return out, sqi, keep


print("=" * (COLS + 2))
print("  SQI 信号质量对比演示    判据：质量等级随干扰单调下降")
print("=" * (COLS + 2))

o = Overlay("/boot/ecg_bd.bit")
time.sleep(1.0)
m = MMIO(ECG, 0x1000)
print("  版本 0x%08X" % m.read(0x14))
# ★ 顺序不能反：0x00 是双用途寄存器（bit3=1 时为主机样本，bit3=0 时才是 FTW）。
#   若上一次测试残留 bit3=1，先写 0x00 会把 83 当成一个样本写掉，FTW 仍为 0，
#   DDS 因此输出恒 0、波形全零。故必须先清控制字，再写频率字。
m.write(0x10, 0x0)                # 先退出主机样本模式（bit3=0）
time.sleep(0.1)
m.write(0x00, 83)                 # 再写 FTW = 72.5 BPM
time.sleep(0.5)
# 自检：确认 DDS 已在出波形（检测计数应随时间增长）
d0 = m.read(0x1C)
time.sleep(0.5)
d1 = m.read(0x1C)
print("  自检：FTW=83，0.5 秒内检测数 %d -> %d" % (d0, d1))

# 状态 A：无干扰
a, sqi_a, keep_a = panel(m, "状态 A：无干扰（仅心电）", 0x1, G, "A")
# 状态 B：注入 50Hz 600 LSB
# ★ 控制字：bit0=缓冲存滤波后  bit2=注入使能  [23:8]=注入幅度
#   上一版漏了 bit2，导致只设幅度而注入器未启动，状态 B 仍是 3 级。
CTL_BUF = 0x1
CTL_INJ = 0x4
b, sqi_b, keep_b = panel(m, "状态 B：注入 50 Hz 工频（600 LSB）",
                         CTL_BUF | CTL_INJ | (600 << 8), Y, "B")

sys.stdout.write("\033[2J\033[H")
print("=" * (COLS + 2))
print("  SQI 信号质量对比    输入条件改变 → 硬件质量等级实时下降")
print("=" * (COLS + 2))
print()
for line in a:
    print(line)
print()
for line in b:
    print(line)
print()
print("  结论：能量保留 %.1f%% → %.1f%%，质量等级 %d → %d"
      % (keep_a, keep_b, sqi_a, sqi_b))
print("  说明：等级由 PL 内的硬件单元给出，未经过任何软件判断")
print("=" * (COLS + 2))
print("  ← 请在此屏截图（Win + Shift + S），保存为 C2_质量对比.png")
print("=" * (COLS + 2))
m.write(0x10, 0)
