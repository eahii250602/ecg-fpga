# -*- coding: utf-8 -*-
"""
ECG-DDS-FPGA  ·  PYNQ 上位机监控脚本
=====================================
功能：
  1. 加载 FPGA overlay（把 PL 配置成心电系统）
  2. 自检 AXI 通路（读版本号 0xEC600001）
  3. 设置心率（写 FTW）
  4. 读回 1024 点心电波形
  5. 读回 RR 计数并换算心率
  6. 画图（含检测阈值参考线）

运行方式（PYNQ 的 Jupyter Notebook 里）：
  把本文件与 ecg_bd.bit / ecg_bd.hwh 放在同一目录，然后：
      %run ecg_monitor.py
  或直接在 Notebook 单元里逐段执行。

寄存器映射（IP 基地址 0x43C00000）：
  0x00  W  REG_FTW        频率控制字 → 改心率
  0x04  W  REG_WAVE_ADDR  波形读地址（0 ~ 1023）
  0x08  R  REG_RR_COUNT   RR 采样点数 → 算 BPM
  0x0C  R  REG_WAVE_DATA  该地址处的波形值（32 位有符号）
  0x14  R  REG_VERSION    固定 0xEC600001（通路自检）
"""

import time
import numpy as np
import matplotlib.pyplot as plt

from pynq import Overlay, MMIO

# ================= 配置 =================
BITFILE       = "ecg_bd.bit"       # ★ 必须与 ecg_bd.hwh 同名！
CLK_FREQ_HZ   = 100_000_000        # PL 时钟（PS 的 FCLK_CLK0）
SAMPLE_FREQ   = 250                # 设计采样率
WAVE_DEPTH    = 1024               # 波形缓冲深度
BASE_FALLBACK = 0x43C00000         # 地址编辑器分配的基地址（备用）

REG_FTW       = 0x00
REG_WAVE_ADDR = 0x04
REG_RR_COUNT  = 0x08
REG_WAVE_DATA = 0x0C
REG_VERSION   = 0x14
VERSION_MAGIC = 0xEC600001


# ================= 工具函数 =================
def to_signed32(v):
    """32 位无符号 → 有符号。Verilog 里做了符号扩展，负数会变成很大的正数。"""
    return v - 0x100000000 if (v & 0x80000000) else v


def bpm_to_ftw(bpm):
    """心率 → 频率控制字： FTW = 2^32 × (BPM/60) / f_clk"""
    f_out = bpm / 60.0
    return int(round(f_out * (2 ** 32) / CLK_FREQ_HZ))


# ================= 1. 加载 overlay =================
print("=" * 60)
print("1. 加载 overlay:", BITFILE)
ol = Overlay(BITFILE)

# 从 .hwh 里找出 IP 的实际基地址（比硬编码可靠）
base = BASE_FALLBACK
for name, info in ol.ip_dict.items():
    if "ecg_axi" in name:
        try:
            base = info["phys_addr"]
            print("   找到 IP '%s'，基地址 0x%08X" % (name, base))
        except (KeyError, TypeError):
            pass
        break
else:
    print("   未在 hwh 中找到 ecg_axi，使用备用地址 0x%08X" % base)

mmio = MMIO(base, 0x10000)


# ================= 2. 自检 =================
ver = mmio.read(REG_VERSION)
ok = (ver == VERSION_MAGIC)
print("2. 版本号自检: 读到 0x%08X，期望 0x%08X -> %s"
      % (ver, VERSION_MAGIC, "通过" if ok else "失败"))
if not ok:
    raise RuntimeError(
        "AXI 通路自检失败！请依次检查：\n"
        "   (a) overlay 是否真的加载成功\n"
        "   (b) 基地址是否为 0x%08X\n"
        "   (c) .bit 与 .hwh 是否同名且同目录" % base)


# ================= 3. 设置心率 =================
TARGET_BPM = 72
ftw = bpm_to_ftw(TARGET_BPM)
mmio.write(REG_FTW, ftw)
print("3. 设定心率 %d BPM -> FTW = %d" % (TARGET_BPM, ftw))


# ================= 4. 等缓冲填满 =================
WAIT_S = WAVE_DEPTH / float(SAMPLE_FREQ) + 1.0     # 4.1s + 1s 余量
print("4. 等待 %.1f 秒让波形缓冲填满 ..." % WAIT_S)
time.sleep(WAIT_S)


# ================= 5. 读心率 =================
rr = mmio.read(REG_RR_COUNT) & 0xFFFF
bpm_meas = (60.0 * SAMPLE_FREQ / rr) if rr else float("nan")
print("5. RR 计数 = %d  ->  实测心率 = %.1f BPM" % (rr, bpm_meas))


# ================= 6. 读波形 =================
print("6. 读取 %d 点波形 ..." % WAVE_DEPTH)
t0 = time.time()
wave = np.zeros(WAVE_DEPTH, dtype=np.int32)
for i in range(WAVE_DEPTH):
    mmio.write(REG_WAVE_ADDR, i)                  # 先写"要读第几个点"
    wave[i] = to_signed32(mmio.read(REG_WAVE_DATA))   # 再读数据
t_read = time.time() - t0
span_s = WAVE_DEPTH / float(SAMPLE_FREQ)
print("   完成：耗时 %.1f ms；波形时间跨度 %.0f ms；占比 %.3f%%"
      % (t_read * 1000.0, span_s * 1000.0, t_read / span_s * 100.0))


# ================= 7. 对齐到 R 波 =================
# 环形缓冲的起点是任意的，旋转一下让图从 R 波（最大值）开始，更美观
peak_idx = int(np.argmax(wave))
wave_aligned = np.roll(wave, -peak_idx)
print("7. 峰值在第 %d 点，已旋转对齐到图起点" % peak_idx)


# ================= 8. 画图 =================
t = np.arange(WAVE_DEPTH) / float(SAMPLE_FREQ)     # 时间轴（秒）
beats = WAVE_DEPTH / float(rr) if rr else 0

fig, ax = plt.subplots(figsize=(13, 4))
ax.plot(t, wave_aligned, linewidth=1.2, color="#c0392b", label="ECG (PL 实时采样)")
ax.axhline(1200, color="gray", linestyle="--", linewidth=0.8,
           label="R 波检测阈值 1200")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Amplitude (12-bit signed)")
ax.set_title("ECG waveform @ %.1f BPM   (rr_count=%d, 约 %.1f 个心跳, 缓存 %d 点)"
             % (bpm_meas, rr, beats, WAVE_DEPTH))
ax.grid(True, alpha=0.3)
ax.legend(loc="upper right")
plt.tight_layout()
plt.show()
