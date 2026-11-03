# -*- coding: utf-8 -*-
"""
ECG-DDS-FPGA · 寄存器访问【分步定位】测试  (绕开 PYNQ 的 MMIO，用裸 /dev/mem)

为什么这样写：
    挂死的 AXI 事务会把整个 CPU 冻住，连 print 都来不及输出。
    所以每一步都把日志【写进 /boot/progress.txt 并立即落盘】。
    一旦挂死 -> 断电重启 -> 取 SD 卡 -> 读 progress.txt -> 就知道卡在第几步。

用法（板子上）：
    python3 regtest.py
    （建议后台跑：  python3 regtest.py > /tmp/r.txt 2>&1 &  ）
"""

import mmap
import os
import struct
import sys
import time

BASE = 0x43C00000
LOGF = "/boot/progress.txt"


def log(msg):
    """写日志：既打印到屏幕，也立即落盘到 SD 卡。"""
    try:
        with open(LOGF, "a") as fh:
            fh.write(msg + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:          # noqa: BLE001
        pass
    print(msg, flush=True)


def main():
    log("=" * 50)
    log("=== START  (regtest) ===")

    log("S1  import pynq")
    from pynq import Overlay, Clocks

    log("S2  set FCLK_CLK0 = 100 MHz")
    Clocks.fclk0_mhz = 100

    log("S3  load overlay (only PYNQ job)")
    Overlay("/home/xilinx/ecg_bd.bit")

    log("S4  open /dev/mem and mmap 0x43C00000")
    f = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    m = mmap.mmap(f, 0x1000, offset=BASE)

    def R(off):
        return struct.unpack("<I", m[off:off + 4])[0]

    def W(off, val):
        m[off:off + 4] = struct.pack("<I", val)

    log("S5  READ  0x14 (version)")
    log("      ver = 0x%08X" % R(0x14))

    log("S6  WRITE 0x00 = 52 (FTW for 72 BPM)")
    W(0x00, 52)

    log("S7  READ  0x00 (readback -> 若为 52 说明写入生效)")
    log("      ftw_readback = %d" % R(0x00))

    log("S8  sleep 5.2 s (fill waveform buffer)")
    time.sleep(5.2)

    log("S9  READ  0x08 (rr_count)")
    rr = R(0x08) & 0xFFFF
    log("      rr = %d" % rr)

    log("S10 READ  0x0C once (waveform data, addr=whatever)")
    log("      wave0 = %d" % R(0x0C))

    log("S11 WRITE 0x04 = 0 (waveform addr = 0)")
    W(0x04, 0)

    log("S12 READ  0x0C again (should be same point)")
    log("      wave0b = %d" % R(0x0C))

    log("S13 loop 1024 x (WRITE 0x04 index, READ 0x0C data)")
    vals = []
    for i in range(1024):
        W(0x04, i)
        v = R(0x0C)
        vals.append(v - (1 << 32) if v >= (1 << 31) else v)
        if i % 128 == 0:
            log("      progress %d/1024" % i)

    log("S14 stats: min=%d max=%d" % (min(vals), max(vals)))

    log("S15 save CSV to /boot/ecg_wave.csv")
    with open("/boot/ecg_wave.csv", "w") as fh:
        fh.write("\n".join(map(str, vals)))

    log("=== DONE  (rr=%d) ===" % rr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
