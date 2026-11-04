#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dma_pattern.py —— 看清 DMA 到底写了什么、写了多少

为什么要清零缓冲：
    PYNQ 的 allocate() 返回 CMA 内存，内容不确定（可能是上次残留）。
    上一次诊断看到 "160/500 非零" 无法判断是 DMA 写的还是垃圾，
    所以这里先把缓冲区全部置 0，再看剩下什么。

要看的三件事：
    1. 非零个数  —— 判断 DMA 实际写了多少个样本
    2. 数据排布  —— int16 视图下若是 [样本, 0, 样本, 0]，说明 16 位数据
                    被放在 32 位字的高半部，属于宽度打包问题
    3. 状态位    —— 传输前后的 DMASR 变化
"""
import time

import numpy as np

from pynq import Overlay, MMIO, allocate

ECG = 0x43C00000
DMA = 0x40400000


def dec(sr):
    n = {0: "Halted", 1: "Idle", 4: "DMAIntErr", 5: "DMASlvErr", 6: "DMADecErr",
         8: "SGIntErr", 9: "SGSlvErr", 10: "SGDecErr", 12: "IOC_Irq", 14: "Err_Irq"}
    return ",".join(v for k, v in n.items() if (sr >> k) & 1) or "(none)"


o = Overlay("/boot/ecg_bd.bit")
time.sleep(1.0)
m = MMIO(ECG, 0x1000)
d = MMIO(DMA, 0x1000)

# 1) 启动 DDS
m.write(0x10, 0)
m.write(0x00, 83)
time.sleep(1.0)

# 2) 清空 DMA 状态（写 1 清除），避免上电残留
d.write(0x34, 0x00005011)
time.sleep(0.1)
print("[A] 清状态后 SR=0x%08X [%s]" % (d.read(0x34), dec(d.read(0x34))))

# 3) 分配并清零缓冲
N = 500
buf = allocate(shape=(N,), dtype=np.int16)
buf[:] = 0
print("[B] 缓冲已清零，nbytes=%d" % buf.nbytes)

# 4) 发起传输
dma = o.axi_dma_0
dma.recvchannel.transfer(buf)
time.sleep(3.0)

sr = d.read(0x34)
print("[C] 3 秒后 SR=0x%08X [%s]  LEN=0x%08X" % (sr, dec(sr), d.read(0x58)))

# 5) 分析写入内容
a16 = np.asarray(buf, dtype=np.int16)
a32 = np.asarray(buf, dtype=np.int32) if buf.nbytes % 4 == 0 else None
nz16 = np.nonzero(a16)[0]
print("\n[D] int16 视图：非零 %d / %d" % (len(nz16), N))
if len(nz16):
    print("    首个非零下标 = %d" % nz16[0])
    print("    最后非零下标 = %d" % nz16[-1])
    print("    前 24 个 = %s" % a16[:24].tolist())
    # 判断"隔一个零"的排布
    even_nz = sum(1 for i in range(0, min(len(a16), 200), 2) if a16[i] != 0)
    odd_nz = sum(1 for i in range(1, min(len(a16), 200), 2) if a16[i] != 0)
    print("    前 200 个里：偶数位非零 %d，奇数位非零 %d" % (even_nz, odd_nz))
    if odd_nz == 0 and even_nz > 20:
        print("    >>> 数据只落在偶数位 → 16 位样本被放在 32 位字的低半部，属正常打包")
    elif even_nz == 0 and odd_nz > 20:
        print("    >>> 数据只落在奇数位 → 样本被放在 32 位字的高半部，需调整视图")
else:
    print("    >>> DMA 一个字节都没写")

print("\n[E] 峰值=%d 均值=%.1f" % (int(np.abs(a16).max()), float(a16.mean())))
print("\n[F] 结论")
if len(nz16) == 0:
    print("    DMA 未写入数据 → 流端没有 tvalid 到达，或 tready 一直为低")
elif len(nz16) >= N - 2:
    print("    全部写满 → 通路完全正常，此前的 160/500 是内存残留")
else:
    print("    只写了 %d/%d → 传输在中途中断" % (len(nz16), N))
