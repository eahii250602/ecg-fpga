#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump_pt_events.py —— 读缓冲：滑动和 + 检测打标（定位漏拍）

缓冲里每个采样拍写一个 32 位数：
  - 正常采样拍：PT 的滑动和（< 0x80000000）
  - 发生过检测的那个采样拍：0x8000_0000 | r_index（R 峰序号）

输出：缓冲内的检测事件列表（地址 + r_index）+ 滑动和峰

用法（板子串口）：
    cd /home/xilinx
    python3 dump_pt_events.py
"""
import time

from pynq import Overlay, MMIO

BASE = 0x43C00000
DEPTH = 1024
DET_FLAG = 0x80000000


def main():
    ol = Overlay('/home/xilinx/ecg_bd.bit')
    mm = MMIO(BASE, 0x1000)
    print('VER 0x%08X (expect 0xEC600002)' % mm.read(0x14))

    mm.write(0x00, 83)          # 62.5MHz 下 = 72.5BPM（每拍 206.99 点，环 1024 点 ≈ 4.1 s）
    time.sleep(6.0)             # 让环填满（1024 点 ≈ 4.1 秒）
    print('det count = %d' % mm.read(0x1C))

    buf = []
    for i in range(DEPTH):
        mm.write(0x04, i)
        buf.append(mm.read(0x0C) & 0xFFFFFFFF)

    dets = [(i, v & 0xFFFF) for i, v in enumerate(buf) if v & DET_FLAG]
    print('--- 检测事件（缓冲内共 %d 个）---' % len(dets))
    for p in dets:
        print('   addr=%4d  r_index=%d' % p)

    sums = [v for v in buf if not (v & DET_FLAG)]
    if sums:
        m = max(sums)
        print('--- 滑动和：max=%d min=%d ---' % (m, min(sums)))
        peaks = []
        for i in range(2, DEPTH - 2):
            v = buf[i]
            if v & DET_FLAG:
                continue
            if v > m // 5 and v >= buf[i - 1] and v > buf[i + 1]:
                peaks.append((i, v))
        print('滑动和峰（>max/5）共 %d 个:' % len(peaks))
        for p in peaks[:10]:
            print('   addr=%4d  val=%d' % p)


if __name__ == '__main__':
    main()
