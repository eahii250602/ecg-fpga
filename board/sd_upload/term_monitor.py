#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""term_monitor.py —— 串口终端里的实时心电波形（可视优化版）

为什么需要这个版本
------------------
板子与笔记本不在同一网段，且当前通过串口 ttyPS0 连接 —— 串口只能传文字，
所以用字符画波形，不依赖网络。

可视化三处优化（针对"人眼看"这一目标）
------------------------------------
1. 【自动居中】用窗口中位数作为基线。
   DDS 信号基线是原始值 0，减 2048 后是 -2048；XADC 真实信号基线在 2048 附近。
   写死任何一个都会让波形贴顶或贴底，所以按窗口自身的中位数对齐。

2. 【开方压缩】高度 ∝ sqrt(|v-base| / amp)。
   心电的 QRS 幅度是 P/T 波的 10 倍以上；线性显示时 P/T 会被压成一条直线。
   开方压缩把小信号抬起来、大信号压下去，这是心电图机的标准做法。

3. 【自适应宽度】读取终端实际列数，窗口按列数决定，
   横向点数越多越接近真实波形。

刷新用 ANSI 光标复位（ESC[H），原地刷新不滚屏。
"""
import os
import sys
import time

import numpy as np
from pynq import Overlay, MMIO

ECG = 0x43C00000
FS = 250.0
POLL = 0.8              # 刷新周期（秒）：0.8s 刷新一次，眼睛跟得上，不再一闪而过
BLOCKS = " ▁▂▃▄▅▆▇█"


def term_size():
    try:
        s = os.get_terminal_size()
        return max(40, min(s.columns - 1, 200)), max(5, min(s.lines - 5, 15))
    except Exception:
        return 100, 9


COLS, ROWS = term_size()
PER = int(FS * POLL)          # 每次读的点数（100 点 = 0.4 秒）
WIN = COLS * 8                # 窗口点数：每列 8 点 → 约 2.5 秒 / 3 个心搏
HIST = max(WIN, 800)


def vreg(m, i):
    m.write(0x04, 0x400 | i)
    return m.read(0x0C) & 0xFFFFFFFF


def hr_from(x):
    if len(x) < 200:
        return 0.0
    v = x.astype(np.float64) - x.mean()

    def ma(a, k):
        k = max(1, int(k))
        return np.convolve(a, np.ones(k) / k, mode="same")
    hp = v - ma(v, FS / 5.0)
    bp = ma(hp, FS / 15.0)
    d = np.diff(bp, prepend=bp[0])
    env = ma(d ** 2, 0.15 * FS)
    if env.max() <= 0:
        return 0.0
    env /= env.max()
    sp = np.abs(np.fft.rfft(env * np.hanning(len(env))))
    fr = np.fft.rfftfreq(len(env), 1 / FS)
    sel = (fr > 0.5) & (fr < 4.0)
    if not sel.any():
        return 0.0
    return float(fr[sel][np.argmax(sp[sel])] * 60.0)


def render(hist, sqi, hr):
    # --- 取窗口并按列压缩（每列取偏离中位数最大的点，保住 QRS 尖峰）---
    seg = hist[-WIN:] if len(hist) >= WIN else np.pad(hist, (WIN - len(hist), 0))
    seg = seg.astype(np.float64)
    base0 = float(np.median(seg))
    step = max(1, len(seg) // COLS)
    n = len(seg) // step
    seg = seg[:n * step].reshape(n, step)
    pick = np.argmax(np.abs(seg - base0), axis=1)
    seg = seg[np.arange(n), pick][-COLS:]

    # --- 自动居中 + 开方压缩 ---
    base = float(np.median(seg))
    amp = max(1.0, float(np.abs(seg - base).max()))
    dev = (seg - base) / amp                      # -1 ~ +1
    hgt = np.sqrt(np.abs(dev)) * np.sign(dev)     # 开方压缩
    hgt = (hgt + 1.0) * 0.5 * (ROWS - 1)          # 映射到 0 ~ ROWS-1

    lines = []
    for r in range(ROWS - 1, -1, -1):
        buf = []
        for i, h in enumerate(hgt):
            hp = hgt[i - 1] if i > 0 else h
            lo, hi = (h, hp) if h <= hp else (hp, h)
            at_v = int(round(h)) == r
            flat = abs(h - hp) < 0.6
            if at_v and flat:
                buf.append("━")          # 平缓段：粗横线（细线看着太弱）
            elif at_v:
                buf.append("█")          # 顶点：实心块，最醒目
            elif lo <= r + 0.5 <= hi:
                buf.append("┃")          # 陡峭段：粗竖线
            else:
                buf.append(" ")
        lines.append("".join(buf))

    color = "\033[32m" if sqi >= 2 else ("\033[33m" if sqi == 1 else "\033[31m")
    q = ["不可信", "可疑", "良好", "优秀"][sqi] if 0 <= sqi <= 3 else "?"
    head = ("%s心率 %5.1f BPM   质量 %s %d/3   250Hz   幅度 %4d   用时 %3.0fs\033[0m"
            % (color, hr, q, sqi, int(amp), time.time() - T0))
    return head + "\n" + "\n".join(lines)


print("=" * 60)
print("串口实时心电监视（Ctrl-C 退出）  终端 %d列×%d行  模式=%s"
      % (COLS, ROWS, "注入50Hz干扰" if (len(sys.argv) > 1 and sys.argv[1].lower() == "inj") else "无干扰"))
print("=" * 60)

o = Overlay("/boot/ecg_bd.bit")
time.sleep(1.0)
m = MMIO(ECG, 0x1000)
xadc = MMIO(0x43C10000, 0x1000)
print("版本 0x%08X" % m.read(0x14))
# 可选参数：
#   python3 term_monitor.py           → DDS 合成波形
#   python3 term_monitor.py inj       → DDS + 50Hz 注入
#   python3 term_monitor.py real      → 真实心电（读 XADC 走主机样本通道）
ARG = sys.argv[1].lower() if len(sys.argv) > 1 else ""
INJ = (ARG == "inj")
REAL = (ARG == "real")
# 顺序不能反：0x00 在 bit3=1 时是主机样本，bit3=0 时才是 FTW
m.write(0x10, 0x0)
time.sleep(0.1)
m.write(0x00, 83)       # DDS 72.5 BPM
time.sleep(0.3)
# bit0=缓冲存滤波后  bit2=注入使能  [23:8]=注入幅度
if REAL:
    m.write(0x10, 0x9)          # bit3=主机样本模式, bit0=缓冲存滤波后
else:
    m.write(0x10, 0x1 | (0x4 if INJ else 0) | ((600 << 8) if INJ else 0))
time.sleep(1.5)

T0 = time.time()
hist = np.zeros(HIST, dtype=np.int16)
addr = 0
sys.stdout.write("\033[2J")
try:
    while True:
        new = np.empty(PER, dtype=np.int16)
        for k in range(PER):
            if REAL:
                # 主机样本模式：读 XADC（VP/VN，偏移 0x20C）→ 写 0x00 推入硬件链
                m.write(0x00, (xadc.read(0x20C) >> 4) & 0xFFF)
            m.write(0x04, addr & 0x3FF)
            new[k] = (m.read(0x0C) & 0xFFFF) - 2048
            addr += 1
        hist = np.concatenate([hist[PER:], new])
        sqi = vreg(m, 0)
        hr = hr_from(hist) if time.time() - T0 > 3 else 0.0
        sys.stdout.write("\033[H" + render(hist, sqi, hr))
        sys.stdout.flush()
except KeyboardInterrupt:
    m.write(0x10, 0)
    print("\n已退出")
