#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pt_check.py —— 上板检查 PT 是否真在 FPGA 里工作（H2-2，2026-11-03 校准版）

★ 2026-11-03 关键修正：板上实测 fclk0 = 62.5 MHz（不是文档里的 100MHz）
   因此 FTW 必须按 62.5MHz 重算，否则 "72BPM" 实际是 45BPM：
       72BPM  → FTW = 2^32*1.2/62.5e6 ≈ 82.4 → 取 83（每拍 206.99 点）
       180BPM → FTW = 2^32*3.0/62.5e6 ≈ 206.2 → 取 206（每拍 83.4 点）
   采样率（分频 250000）已由 IP 的 CLK_FREQ_HZ=62.5MHz 保证为 250Hz。

判据：
   72BPM 时 PT rr ≈ 207（与旧检测器一致）；20 秒检测数应涨 ~24
   180BPM 时 PT rr ≈ 83

用法（板子串口）：
    sudo -s
    source /etc/profile.d/pynq_venv.sh
    source /etc/profile.d/xrt_setup.sh
    cd /home/xilinx
    python3 pt_check.py
"""
import os
import time

DEFAULT_BASE = 0x43C00000
VERSION_MAGIC = 0xEC600003

FTW_72 = 83      # 62.5MHz 下 = 72.5 BPM（206.99 点/拍）
FTW_180 = 206    # 62.5MHz 下 = 180.1 BPM（83.4 点/拍）


def load_overlay(script_dir):
    from pynq import Overlay, Clocks
    ol = Overlay(os.path.join(script_dir, "ecg_bd.bit"))
    try:
        print("[0] PL 实际时钟 fclk0 = %s MHz" % Clocks.fclk0_mhz)
    except Exception as e:
        print("[0] 读 fclk0 失败: %s" % e)
    base = DEFAULT_BASE
    for name, info in ol.ip_dict.items():
        if "ecg_axi" in name:
            try:
                base = info["phys_addr"]
            except (KeyError, TypeError):
                pass
            print("[0] ecg_axi IP '%s' @ 0x%08X" % (name, base))
    return base


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base = load_overlay(script_dir)
    from pynq import MMIO
    mm = MMIO(base, 0x1000)

    ver = mm.read(0x14)
    print("[1] VERSION 0x14 = 0x%08X  (期望 0x%08X) -> %s"
          % (ver, VERSION_MAGIC, "PASS" if ver == VERSION_MAGIC else "FAIL"))
    if ver != VERSION_MAGIC:
        print("    !! 不是含 PT 的新比特流（检查 md5 / 是否加载了旧流）")

    def show(tag):
        old_rr = mm.read(0x08) & 0xFFFF
        pt_rr = mm.read(0x18) & 0xFFFF
        pt_cnt = mm.read(0x1C)
        print("    %s : 旧检测器 rr=0x%04X(%d)   PT rr=0x%04X(%d)   PT 检测数=%d"
              % (tag, old_rr, old_rr, pt_rr, pt_rr, pt_cnt))

    print("[2] 写 FTW=%d（72BPM），等 4 秒 ..." % FTW_72)
    mm.write(0x00, FTW_72)
    time.sleep(4.0)
    show("72BPM")

    print("[3] 写 FTW=%d（180BPM），等 3 秒 ..." % FTW_180)
    mm.write(0x00, FTW_180)
    time.sleep(3.0)
    show("180BPM")

    print("[4] 再写回 FTW=%d（恢复 72BPM），等 1 秒 ..." % FTW_72)
    mm.write(0x00, FTW_72)
    time.sleep(1.0)
    show("恢复72BPM")

    print("[5] 20 秒长测（确认检测率 = 1.2 次/秒）...")
    c0 = mm.read(0x1C)
    t0 = time.time()
    time.sleep(20.0)
    c1 = mm.read(0x1C)
    dt = time.time() - t0
    print("    检测数 %d -> %d，用时 %.2f s，实测心率 = %.1f BPM（期望 ~72）"
          % (c0, c1, dt, (c1 - c0) / dt * 60.0))
    show("长测后")

    print("判据：72BPM 时 PT rr ≈ 207；180BPM 时 ≈ 83；长测心率 ≈ 72 BPM")


if __name__ == "__main__":
    main()