#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""比特流身份校验工具（不依赖任何具体项目）

问题
----
同一块板反复换比特流时，「板上跑的到底是哪一版」靠肉眼无法判断。
文件名相同、大小相同、只有几个寄存器的差别 —— 于是改了 RTL 却以为没生效，
白改好几轮。

做法
----
先算文件 MD5（判断「卡里的文件是不是新的」），
再读设计里的只读版本寄存器（判断「PL 里跑的是不是新的」）。
两者都通过，才能说「跑的是新设计」。

用法
----
    python3 bitstream_identity.py <bit文件> [版本寄存器地址] [期望版本值]

    例：
    python3 bitstream_identity.py /boot/a.bit 0x43C00014 0xEC600008

失效条件
--------
- 设计中没有只读版本寄存器 → 只能比对文件 MD5
- 版本寄存器地址写错 → 会读到相邻寄存器，看起来「版本不对」但其实是地址错
"""
import hashlib
import pathlib
import sys
import time

bit = sys.argv[1] if len(sys.argv) > 1 else None
if not bit:
    print(__doc__)
    sys.exit(1)

p = pathlib.Path(bit)
if not p.exists():
    print("文件不存在: %s" % bit)
    sys.exit(1)

data = p.read_bytes()
print("文件      : %s" % p.name)
print("大小      : %d B" % len(data))
print("MD5       : %s" % hashlib.md5(data).hexdigest().upper())
print("SHA256前16: %s" % hashlib.sha256(data).hexdigest().upper()[:16])

if len(sys.argv) >= 3:
    addr = int(sys.argv[2], 16)
    expect = int(sys.argv[3], 16) if len(sys.argv) >= 4 else None

    from pynq import Overlay, MMIO
    Overlay(bit)
    time.sleep(1.0)
    base = addr & ~0xFFF
    off = addr & 0xFFF
    m = MMIO(base, 0x1000)
    v = m.read(off)
    print("版本寄存器: 0x%08X = 0x%08X" % (addr, v))
    if expect is not None:
        if v == expect:
            print("结论      : ✅ 版本匹配，板上跑的是新设计")
            sys.exit(0)
        print("结论      : ❌ 期望 0x%08X，实际 0x%08X" % (expect, v))
        print("            → 卡里的文件或 PL 里的比特流不是同一版")
        sys.exit(2)
    sys.exit(0)

print("（未提供版本寄存器地址，只做了文件校验）")
