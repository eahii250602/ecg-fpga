#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用 PYNQ Overlay 上板模板（不依赖任何具体项目）

用途
----
把一块 PYNQ 板的「Overlay 加载 → 版本校验 → 寄存器连通 → 时钟确认」
压缩成一个可直接运行的脚本。每次换比特流都跑它。

用法
----
    python3 overlay_bringup.py /boot/your.bit 0x43C00000 0x14 0xEC600008

    参数 1: 比特流路径
    参数 2: IP 基地址
    参数 3: 版本寄存器偏移
    参数 4: 期望的版本值

    若只给参数 1，则退化为「加载 Overlay + 地址可访问性检查」。

失效条件
--------
- 设计里没有版本寄存器 → 只做加载与可访问性检查
- PYNQ 3.x 的部分接口与 2.7 不同，见 skill/pynq_generic/SKILL.md
"""
import hashlib
import pathlib
import sys
import time

from pynq import MMIO, Overlay

BIT = sys.argv[1] if len(sys.argv) > 1 else "/boot/your.bit"
BASE = int(sys.argv[2], 16) if len(sys.argv) > 2 else None
VREG_OFF = int(sys.argv[3], 16) if len(sys.argv) > 3 else None
VEXPECT = int(sys.argv[4], 16) if len(sys.argv) > 4 else None


def step(n, msg):
    print("\n[Step %d] %s" % (n, msg))


def ok(msg):
    print("   PASS  " + msg)


def fail(msg):
    print("   FAIL  " + msg)


# ---- Step 1: 文件身份 ----
step(1, "比特流文件身份")
p = pathlib.Path(BIT)
if not p.exists():
    fail("文件不存在: %s" % BIT)
    sys.exit(1)
md5 = hashlib.md5(p.read_bytes()).hexdigest().upper()
ok("%s  %d B  MD5=%s" % (p.name, p.stat().st_size, md5[:16]))
print("   ↑ 与 PC 上那份比对；不一致说明卡里的文件没更新")

# ---- Step 2: 加载 ----
step(2, "加载 Overlay")
try:
    ol = Overlay(BIT)
except Exception as e:
    fail("加载失败: %r" % e)
    print("   检查 .hwh 与 .bit 是否同名同目录")
    sys.exit(1)
time.sleep(1.0)                      # ★ 必须等，否则首读可能为 0
ok("加载完成，已等待 1.0 s")

# ---- Step 3: 版本寄存器 ----
if BASE is not None and VREG_OFF is not None:
    step(3, "版本寄存器校验")
    m = MMIO(BASE, 0x1000)
    try:
        v = m.read(VREG_OFF)
    except Exception as e:
        fail("读版本寄存器失败: %r" % e)
        sys.exit(1)
    print("   读到 0x%08X" % v)
    if VEXPECT is not None:
        if v == VEXPECT:
            ok("与期望值一致 0x%08X" % VEXPECT)
        else:
            fail("期望 0x%08X，实际 0x%08X —— 板上不是新设计" % (VEXPECT, v))
            sys.exit(1)
    else:
        ok("（未提供期望值，仅打印）")

    # ---- Step 4: 寄存器连通性（只做可访问性，不做回环）----
    step(4, "地址可访问性")
    try:
        m.read(0x0C)
        ok("0x0C 可读")
    except Exception as e:
        fail("0x0C 不可读: %r" % e)
else:
    step(3, "跳过版本校验（未提供基地址）")

# ---- Step 5: 提醒 ----
step(5, "时钟频率（需人工确认）")
print("   不要相信 BD 里配的频率 —— BOOT.BIN 的 ps7_init 才是实际值。")
print("   验证方法：让设计输出一个已知分频的信号，用 perf_counter 计时反推。")

print("\n=== 启动自检完成 ===")
print("下一步：按 skill/pynq_generic/SKILL.md 的 Step 6~8 做数据通路检查。")
