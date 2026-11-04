#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dma_diag.py —— DMA 失败原因诊断（只读 + 一次受控尝试）

目的：把 "[5] transfer length 0" 拆开，看清是
    (a) AXIS 流没进 DMA（时钟未关联 / 接口没接上）
    (b) DMA 启动了但收不到 tvalid
    (c) tready 一直为低

寄存器（AXI DMA，S2MM 方向）
    0x30 S2MM_DMACR    0x34 S2MM_DMASR
    0x48 S2MM_DA       0x58 S2MM_LENGTH
DMASR 位含义：
    bit0  Halted      bit1  Idle
    bit4  DMAIntErr   bit5  DMASlvErr   bit6  DMADecErr
    bit8  SGIntErr    bit9  SGSlvErr    bit10 SGDecErr
    bit12 IOC_Irq     bit14 Err_Irq
"""
import time

import numpy as np

from pynq import Overlay, MMIO, allocate

ECG_BASE = 0x43C00000
DMA_BASE = 0x40400000


def decode(sr):
    names = ["Halted", "Idle", "-", "-",
             "DMAIntErr", "DMASlvErr", "DMADecErr", "-",
             "SGIntErr", "SGSlvErr", "SGDecErr", "-",
             "IOC_Irq", "-", "Err_Irq", "-"]
    out = []
    for i, n in enumerate(names):
        if n != "-" and (sr >> i) & 1:
            out.append(n)
    return ",".join(out) if out else "(none)"


def show(tag, d):
    cr = d.read(0x30)
    sr = d.read(0x34)
    da = d.read(0x48)
    ln = d.read(0x58)
    print("  %-10s CR=0x%08X SR=0x%08X  DA=0x%08X  LEN=0x%08X  [%s]"
          % (tag, cr, sr, da, ln, decode(sr)))
    return sr


def main():
    print("=" * 64)
    print("DMA 诊断")
    print("=" * 64)

    o = Overlay("/boot/ecg_bd.bit")
    time.sleep(1.0)
    m = MMIO(ECG_BASE, 0x1000)
    d = MMIO(DMA_BASE, 0x1000)

    m.write(0x10, 0)
    m.write(0x00, 83)
    time.sleep(1.0)

    # 确认采样在跑
    m.write(0x04, 0)
    nz = 0
    for a in range(0, 1024, 32):
        m.write(0x04, a)
        if (m.read(0x0C) & 0xFFFFFFFF) != 0:
            nz += 1
    print("\n[1] 波形缓冲非零点数 = %d / 32" % nz)

    print("\n[2] 传输前 DMA 状态：")
    show("before", d)

    print("\n[3] 尝试一次 500 样本（1000 字节）的传输：")
    buf = allocate(shape=(500,), dtype=np.int16)
    try:
        dma = o.axi_dma_0
        dma.recvchannel.transfer(buf)
        print("    transfer() 已下发")
        time.sleep(3.0)          # 3 秒足够 500 样本（2 秒）
        show("mid", d)
        try:
            dma.recvchannel.wait()
            print("    wait() 返回 OK")
        except Exception as e:
            print("    wait() 抛异常：%s" % e)
    except Exception as e:
        print("    transfer() 抛异常：%s" % e)

    print("\n[4] 传输后 DMA 状态：")
    show("after", d)

    print("\n[5] 缓冲区前 8 个样本：%s" % np.asarray(buf)[:8].tolist())
    print("    缓冲区非零个数：%d / %d"
          % (int(np.count_nonzero(np.asarray(buf))), len(buf)))

    print("\n[6] 判读：")
    sr = d.read(0x34)
    if sr & 0x10:
        print("    DMAIntErr 置位 → DMA 内部错误（常见于流端长期无 tvalid）")
    if sr & 0x40:
        print("    DMADecErr 置位 → 目标地址译码错误（DDR 地址不对）")
    if int(np.count_nonzero(np.asarray(buf))) == 0:
        print("    缓冲区全零 → 数据没进来")
    else:
        print("    缓冲区有数据 → 通路实际是通的")
    print("\n[7] DebugFS 里看 AXIS 连接（可选）：")
    print("    ls /sys/kernel/debug/clk | head")


if __name__ == "__main__":
    main()
