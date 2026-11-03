#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump_pt_sum.py —— 读波形缓冲（当前存的是 PT 的滑动和 sum_r）

目的：把板上 PT 实际看到的"积分和"序列读回来，与仿真逐点对比，
      判断板上是否漏拍/平顶/阈值异常。

用法（板子串口）：
    cd /home/xilinx
    python3 dump_pt_sum.py
"""
import time

from pynq import Overlay, MMIO

BASE = 0x43C00000
DEPTH = 1024


def main():
    ol = Overlay('/home/xilinx/ecg_bd.bit')
    mm = MMIO(BASE, 0x1000)
    print('VER 0x%08X (expect 0xEC600002)' % mm.read(0x14))

    mm.write(0x00, 52)          # 72BPM
    time.sleep(2.0)             # 让它填满缓冲

    buf = []
    for i in range(DEPTH):
        mm.write(0x04, i)
        buf.append(mm.read(0x0C) & 0xFFFFFFFF)

    mx = max(buf)
    mn = min(buf)
    print('sum buffer: min=%d  max=%d' % (mn, mx))

    th = mx // 5
    peaks = []
    for i in range(2, DEPTH - 2):
        if buf[i] > th and buf[i] >= buf[i - 1] and buf[i] > buf[i + 1]:
            peaks.append((i, buf[i]))
    print('peaks (>max/5) 共 %d 个:' % len(peaks))
    for p in peaks[:12]:
        print('   idx=%d  val=%d' % p)

    if peaks:
        p = peaks[0][0]
        lo = max(0, p - 30)
        hi = min(DEPTH - 1, p + 30)
        print('around peak %d (idx: value):' % p)
        print(' '.join('%d:%d' % (i, buf[i]) for i in range(lo, hi + 1)))


if __name__ == '__main__':
    main()
