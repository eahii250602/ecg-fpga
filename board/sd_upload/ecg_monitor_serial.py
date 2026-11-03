# -*- coding: utf-8 -*-
"""
ECG-DDS-FPGA · 串口 / 无显示器版监控脚本
=========================================
与 Jupyter 版 (ecg_monitor.py) 的区别：
  1. 使用 matplotlib 的 'Agg' 后端 —— 不需要显示器
  2. 把图【存成 PNG 文件】，而不是 plt.show()
  3. 同时把波形数据存成 CSV —— 这是"实测输出与参考结果的比对数据"
  4. 运行提示全部用英文 —— 避免串口控制台编码问题（中文保留在注释里）

用法（板子串口里，cwd 在脚本所在目录）：
    python3 ecg_monitor_serial.py            # 默认 72 BPM
    python3 ecg_monitor_serial.py 120        # 指定 120 BPM

文件放置要求（三个文件必须在同一目录）：
    ecg_bd.bit / ecg_bd.hwh / ecg_monitor_serial.py

输出：
    ecg_waveform_<BPM>bpm.png   心电图
    ecg_wave_<BPM>bpm.csv       波形原始数据（time_s, amp）
    并尝试同时写一份到 /boot（SD 卡 FAT 分区，Windows 可直接读取）

寄存器映射（IP 基地址 0x43C00000）：
    0x00  W  REG_FTW        频率控制字 → 改心率
    0x04  W  REG_WAVE_ADDR  波形读地址（0 ~ 1023）      ★V4
    0x08  R  REG_RR_COUNT   RR 采样点数 → 算 BPM
    0x0C  R  REG_WAVE_DATA  该地址处的波形值（32 位有符号）★V4
    0x14  R  REG_VERSION    固定 0xEC600001（通路自检）
"""

import os
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")            # ★ 关键：无显示器后端
import matplotlib.pyplot as plt

from pynq import Overlay, MMIO

# ================= 配置 =================
OUT_DIR       = os.path.dirname(os.path.abspath(__file__))
BITFILE       = os.path.join(OUT_DIR, "ecg_bd.bit")   # 与 .hwh 同名
BOOT_DIR      = "/boot"          # SD 卡的 FAT 分区（Windows 能读）
CLK_FREQ_HZ   = 100_000_000      # PL 时钟（PS 的 FCLK_CLK0）
SAMPLE_FREQ   = 250              # 设计采样率
WAVE_DEPTH    = 1024             # 波形缓冲深度
BASE_FALLBACK = 0x43C00000       # 地址编辑器分配的基地址（备用）

REG_FTW       = 0x00
REG_WAVE_ADDR = 0x04
REG_RR_COUNT  = 0x08
REG_WAVE_DATA = 0x0C
REG_VERSION   = 0x14
VERSION_MAGIC = 0xEC600001


# ================= 工具函数 =================
def to_signed32(v):
    """32 位无符号 → 有符号（Verilog 做了符号扩展，负数会变成很大的正数）"""
    return v - 0x100000000 if (v & 0x80000000) else v


def bpm_to_ftw(bpm):
    """心率 → 频率控制字：FTW = 2^32 × (BPM/60) / f_clk"""
    return int(round((bpm / 60.0) * (2 ** 32) / CLK_FREQ_HZ))


def main():
    target_bpm = int(sys.argv[1]) if len(sys.argv) > 1 else 72

    print("=" * 64)
    print("ECG-DDS-FPGA monitor (serial / headless)")
    print("  script dir : %s" % OUT_DIR)
    print("  bitfile    : %s" % BITFILE)
    print("  target BPM : %d" % target_bpm)
    print("=" * 64)

    # ---------------- 1. 加载 overlay ----------------
    print("[1] loading overlay ...")
    if not os.path.isfile(BITFILE):
        print("    ERROR: bitfile not found: %s" % BITFILE)
        return 1
    # ★★★ 时钟地雷（2026-10-11 更正）：绝对不要调用 Clocks.fclk0_mhz！
    #
    #   旧认知（错误）：.hwh 记录 62.5MHz，所以要手动设成 100MHz。
    #   真相：.hwh 里 IO PLL = 1600MHz，FCLK0 分频 4×4 = 16 → 实际就是 100MHz。
    #         PYNQ 的 Clocks 类按 1000MHz 的 PLL 基准算，才显示成 62.5MHz（纯显示 bug）。
    #   危害：调用 Clocks.fclk0_mhz = 100 时，PYNQ 会算分频 = 1000/100 = 10，
    #         真实频率变成 1600/10 = 160MHz —— 把 PL 超频 60%，可能引发随机故障！
    #
    #   正确做法：什么都不做。加载 overlay 时 .hwh 的时钟配置已正确生效。
    #   时钟是否真是 100MHz，用下面 [5] 的 rr_count 反推验证：
    #         rr_count ≈ 250 × 60 / BPM   （72 BPM → 约 208）
    ol = Overlay(BITFILE)

    base = BASE_FALLBACK
    for name, info in ol.ip_dict.items():
        if "ecg_axi" in name:
            try:
                base = info["phys_addr"]
                print("    found IP '%s' @ 0x%08X" % (name, base))
            except (KeyError, TypeError):
                pass
            break
    else:
        print("    'ecg_axi' not in hwh, fallback base 0x%08X" % base)

    mmio = MMIO(base, 0x1000)

    # ---------------- 2. 版本号自检 ----------------
    ver = mmio.read(REG_VERSION)
    print("[2] version self-test: read 0x%08X, expect 0x%08X -> %s"
          % (ver, VERSION_MAGIC, "PASS" if ver == VERSION_MAGIC else "FAIL"))
    if ver != VERSION_MAGIC:
        print("    ERROR: AXI path self-test failed.")
        print("    check: overlay loaded? base addr 0x%08X? bit/hwh same name?" % base)
        return 2

    # ---------------- 3. 设置心率 ----------------
    ftw = bpm_to_ftw(target_bpm)
    mmio.write(REG_FTW, ftw)
    print("[3] set BPM=%d -> FTW=%d" % (target_bpm, ftw))

    # ---------------- 4. 等缓冲填满 ----------------
    wait_s = WAVE_DEPTH / float(SAMPLE_FREQ) + 1.0
    print("[4] waiting %.1f s for waveform buffer to fill ..." % wait_s)
    time.sleep(wait_s)

    # ---------------- 5. 读心率 ----------------
    rr = mmio.read(REG_RR_COUNT) & 0xFFFF
    bpm_meas = (60.0 * SAMPLE_FREQ / rr) if rr else float("nan")
    print("[5] rr_count = %d  ->  measured BPM = %.2f" % (rr, bpm_meas))
    print("    时钟自检: 理论 rr_count = %.1f  (明显偏离说明 FCLK0 不是 100MHz)"
          % (60.0 * SAMPLE_FREQ / target_bpm))
    if rr:
        print("    error vs target: %.2f BPM (%.2f %%)"
              % (bpm_meas - target_bpm, (bpm_meas - target_bpm) / target_bpm * 100.0))

    # ---------------- 6. 读波形 ----------------
    print("[6] reading %d waveform points ..." % WAVE_DEPTH)
    t0 = time.time()
    wave = np.zeros(WAVE_DEPTH, dtype=np.int32)
    for i in range(WAVE_DEPTH):
        mmio.write(REG_WAVE_ADDR, i)
        wave[i] = to_signed32(mmio.read(REG_WAVE_DATA))
    t_read = time.time() - t0
    span_s = WAVE_DEPTH / float(SAMPLE_FREQ)
    print("    done: %.1f ms ; waveform span %.0f ms ; ratio %.3f %%"
          % (t_read * 1000.0, span_s * 1000.0, t_read / span_s * 100.0))
    print("    wave stats: min=%d max=%d mean=%.1f"
          % (wave.min(), wave.max(), wave.mean()))

    # ---------------- 7. 对齐到 R 波 ----------------
    peak_idx = int(np.argmax(wave))
    wave_aligned = np.roll(wave, -peak_idx)
    print("[7] peak at index %d, rotated to plot start" % peak_idx)

    # ---------------- 8. 画图 + 存文件 ----------------
    t = np.arange(WAVE_DEPTH) / float(SAMPLE_FREQ)
    beats = WAVE_DEPTH / float(rr) if rr else 0.0

    fig, ax = plt.subplots(figsize=(13, 4))
    ax.plot(t, wave_aligned, linewidth=1.2, color="#c0392b",
            label="ECG (PL real-time samples)")
    ax.axhline(1200, color="gray", linestyle="--", linewidth=0.8,
               label="R-wave threshold 1200")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude (12-bit signed)")
    ax.set_title("ECG waveform @ %.2f BPM  (rr_count=%d, ~%.1f beats, %d points)"
                 % (bpm_meas, rr, beats, WAVE_DEPTH))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    plt.tight_layout()

    png_name = "ecg_waveform_%dbpm.png" % target_bpm
    png_path = os.path.join(OUT_DIR, png_name)
    fig.savefig(png_path, dpi=120, bbox_inches="tight")
    print("[8] figure saved: %s" % png_path)

    # 尝试也写一份到 /boot（FAT 分区）→ 取 SD 卡后 Windows 可直接看
    try:
        boot_png = os.path.join(BOOT_DIR, png_name)
        fig.savefig(boot_png, dpi=120, bbox_inches="tight")
        print("    also saved to: %s" % boot_png)
    except Exception as exc:                       # noqa: BLE001
        print("    NOTE: cannot write to %s (%s)" % (BOOT_DIR, exc))
        print("          -> copy manually: sudo cp %s %s/" % (png_path, BOOT_DIR))

    # ---------------- 9. 存 CSV（实测数据，报告要用） ----------------
    csv_name = "ecg_wave_%dbpm.csv" % target_bpm
    csv_path = os.path.join(OUT_DIR, csv_name)
    np.savetxt(csv_path, np.column_stack((t, wave_aligned)),
               delimiter=",", header="time_s,amp", comments="")
    print("[9] data saved: %s" % csv_path)
    try:
        boot_csv = os.path.join(BOOT_DIR, csv_name)
        np.savetxt(boot_csv, np.column_stack((t, wave_aligned)),
                   delimiter=",", header="time_s,amp", comments="")
        print("    also saved to: %s" % boot_csv)
    except Exception as exc:                       # noqa: BLE001
        print("    NOTE: cannot write CSV to %s (%s)" % (BOOT_DIR, exc))

    print("=" * 64)
    print("DONE.  rr_count=%d  BPM=%.2f  read_time=%.1f ms"
          % (rr, bpm_meas, t_read * 1000.0))
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
