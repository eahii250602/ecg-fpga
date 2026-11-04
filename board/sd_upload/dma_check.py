#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dma_check.py —— v6b 验收：AXI-Stream + AXI DMA 环形采集

设计要点（每条都对应当前已知的坑）
----------------------------------
1. Overlay() 会重载比特流并复位全部硬件 → 整个流程必须在【同一进程内】完成。
2. 先读 DMA 状态寄存器（只读），确认 DMA 在地址映射里且已退出复位，
   再发起传输——否则 wait() 可能永久阻塞。
3. 传输长度换算：流宽 16 位、内存宽 32 位 → DMA 把两个样本打包进一个 32 位字。
   因此 Python 侧拿到的字节序列仍是【连续的 int16】。
       N 个样本 = 2N 字节
4. 判据全部有物理依据：
   - 波形峰值应接近 2047（DDS 模板峰值，12 位满量程）
   - 均值应接近 0（心电交流信号）
   - 相邻样本不能全等（否则说明没在采样）

地址：DMA 控制寄存器 0x40400000，S2MM 状态在 +0x34，S2MM 控制 +0x30
"""
import sys
import time

import numpy as np

from pynq import Overlay, MMIO, allocate

ECG_BASE = 0x43C00000
DMA_BASE = 0x40400000
REG_VER, REG_FTW, REG_CTL = 0x14, 0x00, 0x10

N = 2500          # 采样点数（250 Hz 下 = 10 秒）


def main():
    print("=" * 60)
    print("v6b 验收：AXI-Stream + AXI DMA")
    print("=" * 60)

    o = Overlay("/boot/ecg_bd.bit")
    time.sleep(1.0)
    m = MMIO(ECG_BASE, 0x1000)

    ver = m.read(REG_VER)
    print("\n[1] ecg_axi 版本 = 0x%08X" % ver)
    if ver != 0xEC600007:
        print("    !! 期望 0xEC600007 —— 比特流不对")
        return 1

    print("\n[2] Overlay 中的 IP：")
    for k in sorted(o.ip_dict.keys()):
        print("      %s" % k)

    # ---- 只读检查 DMA 状态（不阻塞）----
    d = MMIO(DMA_BASE, 0x1000)
    sr = d.read(0x34)          # S2MM_DMASR
    cr = d.read(0x30)          # S2MM_DMACR
    halted = (sr >> 0) & 1
    idle = (sr >> 1) & 1
    print("\n[3] S2MM_DMASR = 0x%08X  (halted=%d idle=%d)" % (sr, halted, idle))
    print("    S2MM_DMACR = 0x%08X" % cr)
    if halted == 0 and idle == 0 and sr == 0xFFFFFFFF:
        print("    !! 读回全 1，DMA 不在地址映射里")
        return 1

    # ---- 让 DDS 输出 72.5 BPM ----
    m.write(REG_CTL, 0)
    m.write(REG_FTW, 83)
    time.sleep(0.5)
    print("\n[4] DDS 已启动（FTW=83，72.5 BPM）")

    # ---- 前置检查：用寄存器通路确认采样确实在跑 ----
    # 若这里就是 0，说明 sample_tick 没动，DMA 的 wait() 会永久阻塞，
    # 所以必须先在这里拦住，而不是让程序挂死。
    m.write(0x04, 0)
    vals = []
    for addr in range(0, 1024, 64):
        m.write(0x04, addr)
        vals.append(m.read(0x0C) & 0xFFFFFFFF)
    nz = sum(1 for v in vals if v != 0)
    print("    波形缓冲抽样：%d/%d 非零" % (nz, len(vals)))
    if nz == 0:
        print("    !! 采样链路无数据，停止（避免 DMA wait 永久阻塞）")
        return 1

    # ---- 用 PYNQ 的 DMA 驱动 ----
    try:
        dma = o.axi_dma_0
    except Exception as e:
        print("\n!! o.axi_dma_0 取不到：%s" % e)
        print("   说明 PYNQ 没有绑定 DMA 驱动，需改用 MMIO 直接编程")
        return 1

    buf = allocate(shape=(N,), dtype=np.int16)
    print("\n[5] 缓冲区 %.1f KB，开始传输 %d 样本（约 10 秒）..."
          % (buf.nbytes / 1024.0, N))

    t0 = time.time()
    dma.recvchannel.transfer(buf)
    dma.recvchannel.wait()
    el = time.time() - t0

    x = np.asarray(buf, dtype=np.int16).astype(np.int32)
    print("\n[6] 传输完成，用时 %.1f 秒" % el)
    print("    样本数 = %d" % len(x))
    print("    峰值   = %d / %d" % (int(np.abs(x).max()), 2047))
    print("    均值   = %.1f" % x.mean())
    print("    标准差 = %.1f" % x.std())
    print("    前 12 个 = %s" % x[:12].tolist())
    uniq = len(np.unique(x))
    print("    不同取值个数 = %d" % uniq)

    # ---- 判据 ----
    checks = [
        ("样本数正确", len(x) == N),
        ("用时在 8~20 秒（10 秒理论值）", 8.0 <= el <= 20.0),
        ("峰值接近 12 位满量程", 1500 <= int(np.abs(x).max()) <= 2047),
        ("均值接近 0", abs(x.mean()) < 200),
        ("样本有变化（确实在采样）", uniq > 50),
    ]
    print("\n[7] 判据：")
    ok = True
    for name, r in checks:
        print("      %s  %s" % ("PASS" if r else "FAIL", name))
        ok = ok and r

    sr2 = d.read(0x34)
    print("\n[8] 传输后 S2MM_DMASR = 0x%08X" % sr2)

    print("\n" + "=" * 60)
    print("总结：%s" % ("PASS" if ok else "FAIL"))
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
