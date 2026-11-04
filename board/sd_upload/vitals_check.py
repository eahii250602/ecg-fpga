#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vitals_check.py —— v6a 验收：硬件 SQI 与硬件 HRV 累加器

版本要求：0xEC600006

虚拟寄存器访问方式（不扩 AXI 地址宽度）：
    mmio.write(0x04, 0x400 + idx)   # bit10 = 1 → 走虚拟寄存器
    v = mmio.read(0x0C)

    idx 0 : SQI 质量等级 0~3（0 不可信 / 1 可疑 / 2 良好 / 3 优秀）
    idx 1 : 窗口内 RR 个数 n
    idx 2 : Σrr（采样点数）
    idx 3 : Σrr²
    idx 4 : ΣΔrr²
    idx 5 : 窗口已满标志
    idx 6 : 输入能量 acc_in
    idx 7 : 滤波后能量 acc_out

判据
----
A. SQI 分级：不注入时应为 3（优秀）；注入 50Hz(600) 后应 ≤1（干扰占主导）
B. HRV 累加：恒定心率下，四个累加器必须满足恒等式
       Σrr  = n × rr
       Σrr² = n × rr²
       ΣΔrr² = 0（因为相邻 rr 相等）
   误差必须为 0——这是纯算术，任何偏差都说明硬件有问题
"""
import math
import time

import numpy as np
from pynq import Overlay, MMIO

ECG_BASE = 0x43C00000
REG_FTW, REG_WADDR, REG_WDATA, REG_CTL, REG_VER = 0x00, 0x04, 0x0C, 0x10, 0x14
REG_PT_RR = 0x18
BIT_BUF, BIT_PT, BIT_INJ, BIT_HOST = 1, 2, 4, 8
VREG_BASE = 0x400
VERSION_EXPECT = 0xEC600006


def vreg(m, idx):
    m.write(REG_WADDR, VREG_BASE | idx)
    return m.read(REG_WDATA) & 0xFFFFFFFF


def main():
    print("=" * 66)
    print("v6a 验收：硬件 SQI + 硬件 HRV 累加器")
    print("=" * 66)

    Overlay("/boot/ecg_bd.bit")
    time.sleep(1.0)
    m = MMIO(ECG_BASE, 0x1000)

    ver = m.read(REG_VER)
    print("\n[0] 版本号 = 0x%08X" % ver)
    if ver != VERSION_EXPECT:
        print("    !! 期望 0x%08X —— 比特流不是 v6a" % VERSION_EXPECT)
        return
    print("    OK：含 vitals_hw")

    # ---------------- A. SQI 分级 ----------------
    print("\n" + "-" * 66)
    print("[A] 信号质量分级（判据：不注入=3；注入 50Hz 后 ≤1）")
    print("-" * 66)

    m.write(REG_FTW, 83)                      # 72.5 BPM
    m.write(REG_CTL, 0)                       # 不注入，原始波形
    time.sleep(2.0)
    lv0 = vreg(m, 0)
    ain0, aout0 = vreg(m, 6), vreg(m, 7)
    print("    A1 不注入   ：等级=%d  输入能量=%d  滤波后能量=%d  比值=%.1f%%"
          % (lv0, ain0, aout0, 100.0 * aout0 / max(ain0, 1)))

    m.write(REG_CTL, (600 << 8) | BIT_INJ)     # 注入 50Hz
    time.sleep(3.0)
    lv1 = vreg(m, 0)
    ain1, aout1 = vreg(m, 6), vreg(m, 7)
    print("    A2 注入600 ：等级=%d  输入能量=%d  滤波后能量=%d  比值=%.1f%%"
          % (lv1, ain1, aout1, 100.0 * aout1 / max(ain1, 1)))

    ok_sqi = (lv0 == 3) and (lv1 <= 1)
    print("    A3 判定：%s（不注入 %d，注入 %d）"
          % ("PASS" if ok_sqi else "FAIL", lv0, lv1))

    # ---------------- B. HRV 累加恒等式 ----------------
    print("\n" + "-" * 66)
    print("[B] HRV 累加（判据：恒定心率下几何恒等式误差为 0）")
    print("-" * 66)

    # ★2026-11-04 修正：原用例同时开着 50Hz 注入与 FTW=206（180 BPM），
    #   心电峰值 2047 叠加 600 注入后 12 位饱和削顶，PT 无法检测 → det_cnt 不涨 → n=0。
    #   现改为：关闭注入、用 FTW=166（145 BPM，RR=104），64 拍约 27 秒。
    m.write(REG_CTL, 1 << 4)                   # 只置 clear
    time.sleep(0.3)
    m.write(REG_CTL, 0)                        # 放开 clear，无注入
    m.write(REG_FTW, 166)                      # 145 BPM
    print("    设置 FTW=166（145 BPM，无注入），等待 64 个 RR 间期（约 27 秒）...")

    t0 = time.time()
    while time.time() - t0 < 40:
        if vreg(m, 5):                         # ready 标志
            break
        time.sleep(0.5)
    el = time.time() - t0

    n = vreg(m, 1)
    s1 = vreg(m, 2)
    s2 = vreg(m, 3)
    sd = vreg(m, 4)
    rr = m.read(REG_PT_RR) & 0xFFFF
    ready = vreg(m, 5)

    print("    用时 %.1f s，ready=%d" % (el, ready))
    print("    n=%d  RR=%d 点" % (n, rr))
    print("    Σrr   = %d   期望 %d" % (s1, n * rr))
    print("    Σrr²  = %d   期望 %d" % (s2, n * rr * rr))
    print("    ΣΔrr² = %d   期望 0" % sd)

    ok_hrv = (n >= 63) and (s1 == n * rr) and (s2 == n * rr * rr) and (sd == 0)
    print("\n    B 判定：%s" % ("PASS" if ok_hrv else "FAIL"))

    if n > 1:
        mean_rr = s1 / n
        var = s2 / n - mean_rr ** 2
        sdnn = math.sqrt(max(var, 0)) / 250.0 * 1000
        rmssd = math.sqrt(sd / max(n - 1, 1)) / 250.0 * 1000
        print("    （PS 侧换算）SDNN=%.2f ms  RMSSD=%.2f ms（恒定心率应为 0）"
              % (sdnn, rmssd))

    m.write(REG_CTL, 0)
    print("\n" + "=" * 66)
    print("总结：SQI %s / HRV %s" % ("PASS" if ok_sqi else "FAIL",
                                    "PASS" if ok_hrv else "FAIL"))
    print("=" * 66)


if __name__ == "__main__":
    main()
