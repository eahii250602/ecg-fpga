#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ecg_monitor_xadc.py —— D3：从 XADC 读真实心电（V_P/V_N = DRP 0x03）

流程：
  1) Overlay 加载比特流（不做这一步读出来全是 0 —— 见 pitfalls D6）
  2) 从 .hwh 取 XADC 基地址
  3) 以 250Hz 循环读 DRP 0x03（12 位码在 [15:4]）
  4) 存 CSV + PNG（PNG/CSV 同时写 /boot，Windows 可直接打开）

用法（板子串口）：
    sudo -s
    source /etc/profile.d/pynq_venv.sh
    cd /home/xilinx
    python3 ecg_monitor_xadc.py          # 采 10 秒
    python3 ecg_monitor_xadc.py 20       # 采 20 秒

判据（下午实验室）：
  电压在 0.1~0.9V 之间随心跳周期波动，波形上能看到周期性 QRS 尖峰；
  若全 0 / 恒定不变 → 看脚本末尾的提示。
"""
import os
import sys
import time

import numpy as np

FS = 250.0
DRP_VP_VN = 0x03
REG_OFFSET_BASE = 0x200
DEFAULT_XADC_BASE = 0x43C10000


def load_overlay(script_dir):
    bitfile = os.path.join(script_dir, "ecg_bd.bit")
    from pynq import Overlay
    ol = Overlay(bitfile)
    xadc_base = None
    for name, info in ol.ip_dict.items():
        if "xadc" in name:
            try:
                xadc_base = info["phys_addr"]
            except (KeyError, TypeError):
                xadc_base = None
            print("[0] XADC IP '%s' @ 0x%08X" % (name, xadc_base or DEFAULT_XADC_BASE))
    if xadc_base is None:
        print("    !! hwh 里没有 xadc，回退 0x%08X" % DEFAULT_XADC_BASE)
        xadc_base = DEFAULT_XADC_BASE
    return xadc_base


def draw_png(path, v, secs):
    try:
        from PIL import Image, ImageDraw
    except Exception as e:
        print("    (PIL 不可用，跳过 PNG: %s)" % e)
        return False
    n = len(v)
    W, H = 1000, 380
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    mn, mx = float(v.min()), float(v.max())
    span = max(1e-6, mx - mn)

    def X(i):
        return 20 + int(i * (W - 40) / max(1, n - 1))

    def Y(val):
        return H - 30 - int((val - mn) * (H - 60) / span)

    step = max(1, n // 2000)
    pts = [(X(i), Y(float(v[i]))) for i in range(0, n, step)]
    d.line(pts, fill=(0, 0, 0), width=1)
    d.text((10, 5), "XADC V_P/V_N  %.1f s @250Hz   min=%.4f max=%.4f V" % (secs, mn, mx), fill=(0, 0, 0))
    img.save(path)
    print("[3] 波形图: %s" % path)
    return True


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    script_dir = os.path.dirname(os.path.abspath(__file__))

    xadc_base = load_overlay(script_dir)
    from pynq import MMIO
    mm = MMIO(xadc_base, 0x400)

    n = int(secs * FS)
    print("[1] 采集 %.1f 秒（%d 点 @ %.0f Hz）..." % (secs, n, FS))
    t = np.zeros(n)
    c = np.zeros(n, dtype=np.int64)
    v = np.zeros(n)

    t0 = time.time()
    period = 1.0 / FS
    for i in range(n):
        raw = mm.read(REG_OFFSET_BASE + 4 * DRP_VP_VN)
        code = (raw >> 4) & 0xFFF
        t[i] = i / FS
        c[i] = code
        v[i] = code * 1.0 / 4096.0
        nxt = t0 + (i + 1) * period
        dt = nxt - time.time()
        if dt > 0:
            time.sleep(dt)

    print("[2] 电压范围: min=%.4f  max=%.4f  mean=%.4f V"
          % (v.min(), v.max(), v.mean()))

    csv_path = os.path.join(script_dir, "xadc_ecg.csv")
    with open(csv_path, "w", encoding="ascii") as f:
        f.write("time_s,code,volt\n")
        for i in range(n):
            f.write("%.4f,%d,%.5f\n" % (t[i], int(c[i]), v[i]))
    print("    CSV: %s" % csv_path)

    png_ok = draw_png(os.path.join(script_dir, "xadc_ecg.png"), v, secs)

    # 写一份到 /boot（FAT，Windows 可读）
    try:
        import shutil
        shutil.copy(csv_path, "/boot/xadc_ecg.csv")
        if png_ok:
            shutil.copy(os.path.join(script_dir, "xadc_ecg.png"), "/boot/xadc_ecg.png")
        print("[4] 已同时写 /boot/xadc_ecg.csv (+png)")
    except Exception as e:
        print("    (写 /boot 失败: %s)" % e)

    # ---- 判据提示 ----
    print("[5] 判据：电压应在 0.1~0.9V 内随心跳周期波动（QRS 尖峰）")
    if v.max() < 0.02:
        print("    !! 读数接近 0：检查 ① overlay 是否加载 ② J5 接线 ③ AD8232 供电")
    elif (v.max() - v.min()) < 0.005:
        print("    !! 读数几乎不变：检查 AD8232 OUT 是否接到分压中点、SDN 是否拉高")
    else:
        print("    OK：电压有波动，把 PNG/CSV 贴回来，我看波形。")


if __name__ == "__main__":
    main()
