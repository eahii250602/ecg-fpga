#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dbg_pt_timeline.py —— PT 时间线诊断（板上跑，查"3 拍后不再检测"）

输出：每 0.5 秒一行，old_rr / pt_rr / det（PT 累计检测数）
用法（板子串口）：
    cd /home/xilinx
    python3 dbg_pt_timeline.py
"""
import time

from pynq import Overlay, MMIO

BASE = 0x43C00000


def main():
    ol = Overlay('/home/xilinx/ecg_bd.bit')
    mm = MMIO(BASE, 0x1000)
    print('VER 0x%08X (expect 0xEC600002)' % mm.read(0x14))

    def dump(tag):
        print('%s  old_rr=%d  pt_rr=%d  det=%d'
              % (tag, mm.read(0x08) & 0xFFFF, mm.read(0x18) & 0xFFFF, mm.read(0x1C)))

    mm.write(0x00, 52)
    print('--- 72BPM (FTW=52) ---')
    for i in range(12):
        time.sleep(0.5)
        dump('t=%.1f' % (0.5 * (i + 1)))

    mm.write(0x00, 129)
    print('--- 180BPM (FTW=129) ---')
    for i in range(10):
        time.sleep(0.5)
        dump('t=%.1f' % (0.5 * (i + 1)))


if __name__ == '__main__':
    main()
