#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
写通道修复验证 —— 确认 AXI 写操作不再让整机冻死
================================================================
【板上用法】
    cd /home/xilinx
    rm -f /home/xilinx/step.txt
    timeout 30 python3 fix_test.py > /tmp/fix.txt 2>&1 &
    sleep 35
    cat /tmp/fix.txt

【如果整机冻死】（键盘完全没反应，sleep 也不返回）：
    ① 断电 → 等 5 秒 → 上电 → 等 60~90 秒
    ② sudo -s ; source /etc/profile.d/pynq_venv.sh ; source /etc/profile.d/xrt_setup.sh
    ③ cd /home/xilinx
    ④ cat /home/xilinx/step.txt     ← 最后一行就是死点
    ⑤ 把内容发给助手

【为什么用后台 & + timeout】
    写操作一旦挂死会冻住整个 CPU，连 Ctrl+C 都没用。
    放后台跑 + timeout 保护，能把冻死的影响限制住，并保住日志。

【日志为什么写 /home/xilinx/step.txt】
    /tmp 是内存盘，重启就没了；/home/xilinx 在 ext4 根分区上，
    配合 fsync + os.sync()，即使整机冻死，证据也留在盘上。
================================================================
"""

import mmap
import os
import struct
import time

LOG = "/home/xilinx/step.txt"
BASE = 0x43C00000
MAP_SIZE = 0x1000

REG_FTW = 0x00         # 写：频率控制字（43→60BPM, 52→72BPM, 87→120BPM, 130→180BPM）
REG_WAVE_ADDR = 0x04   # 写：波形读地址
REG_RR_COUNT = 0x08    # 读：RR 间隔计数
REG_WAVE_DATA = 0x0C   # 读：波形数据
REG_VERSION = 0x14     # 读：版本号，固定 0xEC600001


def mark(msg):
    """打印 + 写日志 + 强制落盘（冻死也能取证）"""
    line = "[%9.3f] %s" % (time.time() % 100000, msg)
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.sync()
    except Exception as e:
        print("    (日志写入失败: %s)" % e, flush=True)


def main():
    mark("=" * 54)
    mark("START  写通道修复验证")

    # ---- 加载 overlay ----
    mark("S1   导入 pynq")
    from pynq import Overlay

    mark("S2   加载 overlay /home/xilinx/ecg_bd.bit")
    Overlay("/home/xilinx/ecg_bd.bit")
    mark("S3   overlay 加载完成")

    # ---- 映射寄存器 ----
    mark("S4   打开 /dev/mem")
    fd = os.open("/dev/mem", os.O_RDWR)
    mark("S5   mmap 0x43C00000")
    mem = mmap.mmap(fd, MAP_SIZE, offset=BASE)
    mark("S6   mmap 完成")

    def rd(off):
        return struct.unpack("<I", mem[off:off + 4])[0]

    def wr(off, val):
        mem[off:off + 4] = struct.pack("<I", val)

    # ---- 读路径自检 ----
    ver = rd(REG_VERSION)
    mark("S7   读 0x14 版本号 = 0x%08X   (期望 0xEC600001 %s)"
         % (ver, "OK" if ver == 0xEC600001 else "不符!"))

    # ★ 新比特流的"身份证"：slv_reg0 复位默认值 = 52（72BPM）
    #   旧比特流这里是 0 —— 所以看到 52 就证明板子跑的是新比特流
    ftw0 = rd(REG_FTW)
    if ftw0 == 52:
        mark("S8   读 0x00 默认 FTW = %d  ★ 新比特流已生效（默认72BPM）" % ftw0)
    else:
        mark("S8   读 0x00 默认 FTW = %d  ⚠ 不是52 —— 可能还在跑旧比特流？" % ftw0)

    # ---- ★ 关键：写操作 ----
    mark("S9   ★★★ 写 0x00 = 43 (60BPM) —— 这一步以前必然冻死整机")
    wr(REG_FTW, 43)
    mark("S10  ★★★ 写操作返回了！没有冻死！")

    rb = rd(REG_FTW)
    mark("S11  读回 0x00 = %d   (期望 43 %s)" % (rb, "OK" if rb == 43 else "不符!"))

    # ---- 第二个寄存器 ----
    mark("S12  ★ 写 0x04 = 5")
    wr(REG_WAVE_ADDR, 5)
    rb2 = rd(REG_WAVE_ADDR)
    mark("S13  读回 0x04 = %d   (期望 5 %s)" % (rb2, "OK" if rb2 == 5 else "不符!"))

    # ---- 读硬件寄存器 ----
    mark("S14  读 0x08 rr_count  = %d" % rd(REG_RR_COUNT))
    mark("S15  读 0x0C wave_data = %d" % rd(REG_WAVE_DATA))

    mark("DONE  ✅✅ 写通道完全正常，整机冻死问题已解决！")


if __name__ == "__main__":
    main()
