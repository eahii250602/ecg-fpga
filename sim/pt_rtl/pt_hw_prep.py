#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pt_hw_prep.py —— RTL 化前的测量与系数生成（H2 第一步）

做三件事：
 1) 复现 Python 参考的中间信号（带通/微分/平方/积分），看数值范围 → 定 RTL 位宽
 2) 测出"积分峰位置"相对"R 峰真值位置"的固定延迟 → RTL 输出对齐用
 3) 把 61 抽头带通系数转成 Q1.15 定点 → out/pt_bp_coef.mem（RTL $readmemh）
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# pan_tompkins.py 在隔壁 pt_golden 目录
sys.path.insert(0, os.path.join(HERE, "..", "pt_golden"))
sys.path.insert(0, HERE)
import pan_tompkins as pt  # noqa: E402


def main():
    rom = pt.load_rom(pt.find_rom())
    clean = pt.dds_wave(rom)

    rng = np.random.default_rng(20261026)
    t = np.arange(pt.NSAMP) / pt.FS
    noisy = (clean
             + 400.0 * np.sin(2 * np.pi * 50.0 * t)
             + 300.0 * np.sin(2 * np.pi * 0.3 * t)
             + rng.normal(0.0, 100.0, pt.NSAMP))
    noisy = np.clip(np.round(noisy), -2048, 2047).astype(np.int64)

    h = pt.bandpass_coef(5.0, 15.0, 61)
    xf = pt.causal_fir(noisy, h)
    d = pt.derivative5(xf)
    sq = d * d
    integ = pt.moving_avg(sq, 38)

    print("xf  范围: [%.0f, %.0f]" % (xf.min(), xf.max()))
    print("d   范围: [%.0f, %.0f]" % (d.min(), d.max()))
    print("sq  最大值: %.3e" % sq.max())
    print("integ 最大值: %.3e   均值: %.3e" % (integ.max(), integ.mean()))

    # 积分域候选峰（min_dist=50）
    idx = np.where((integ[1:-1] >= integ[:-2]) & (integ[1:-1] > integ[2:]))[0] + 1
    cand = []
    for i in idx:
        if not cand or i - cand[-1] >= 50:
            cand.append(i)
        elif integ[i] > integ[cand[-1]]:
            cand[-1] = i
    cand = np.array(cand)
    print("integ 候选峰数: %d" % len(cand))
    print("前 5 个候选峰 (位置, 值): %s"
          % [(int(c), int(integ[c])) for c in cand[:5]])

    # 每个黄金峰最近的积分候选峰 → 偏移统计
    golden = pt.analytic_peaks(clean)
    offs = []
    for g in golden:
        j = cand[int(np.argmin(np.abs(cand - g)))]
        offs.append(int(j - g))
    print("黄金峰位置: %s" % list(map(int, golden)))
    print("积分峰相对黄金峰偏移: %s" % offs)
    print("偏移均值: %.1f  范围: [%d, %d]" % (np.mean(offs), min(offs), max(offs)))

    # 冷启动参考：前 100 个采样内 integ 的最大值（噪声峰水平）vs 第一拍 QRS 峰
    print("样本 0..99 的 integ 最大值: %.0f" % integ[:100].max())
    print("第一拍 QRS 附近(60..120) integ 最大值: %.0f" % integ[60:121].max())

    # Q1.15 系数导出
    cq = np.clip(np.round(h * 32768.0), -32768, 32767).astype(np.int64)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "pt_bp_coef.mem"), "w", encoding="ascii") as f:
        for v in cq:
            f.write("%04X\n" % (int(v) & 0xFFFF))
    print("已写 out/pt_bp_coef.mem（61 个 Q1.15 系数，十六进制补码）")


if __name__ == "__main__":
    main()
