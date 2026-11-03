#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""design_iir.py —— D4/D5 滤波链设计（最终方案：50Hz 陷波 + 40Hz 低通）

采样率 250Hz（2026-11-03 时钟修正后的真实值）。

★ 为什么只有两级（数字高通被否决）：
  0.5Hz 二阶高通在 250Hz 下极点半径 r=0.9911，A(1)=1+a1+a2=1.6e-4，
  输出量化误差被反馈放大 1/A(1) ≈ 6390 倍 —— 16 位定点实测误差最好只有
  140 LSB（判据 2 LSB），结构性不可行（详见 [5] 的实测对比）。
  基线漂移改由三处负责：AD8232 模块的硬件高通（~0.5Hz）、PT 内部 5–15Hz
  带通（检测用）、PS 软件（显示用）。这是"把功能放到合适的域"的取舍。

两级级联，每级二阶 IIR（biquad），Direct Form I：
    y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]

★ 定点格式 Q2.14（±2，1/16384）：Q1.15 装不下高通系数 -1.98（实测踩过）

输出：out/filt_coef.json
"""
import json
import math
import os

import numpy as np

FS = 250.0
FRAC = 14
SCALE = float(1 << FRAC)
COEF_MIN, COEF_MAX = -32768, 32767

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def notch(f0, Q):
    w0 = 2.0 * math.pi * f0 / FS
    alpha = math.sin(w0) / (2.0 * Q)
    b = [1.0, -2.0 * math.cos(w0), 1.0]
    a = [1.0 + alpha, -2.0 * math.cos(w0), 1.0 - alpha]
    return _norm(b, a)


def lowpass(f0, Q):
    w0 = 2.0 * math.pi * f0 / FS
    alpha = math.sin(w0) / (2.0 * Q)
    c = math.cos(w0)
    b = [(1.0 - c) / 2.0, 1.0 - c, (1.0 - c) / 2.0]
    a = [1.0 + alpha, -2.0 * c, 1.0 - alpha]
    return _norm(b, a)


def highpass(f0, Q):
    w0 = 2.0 * math.pi * f0 / FS
    alpha = math.sin(w0) / (2.0 * Q)
    c = math.cos(w0)
    b = [(1.0 + c) / 2.0, -(1.0 + c), (1.0 + c) / 2.0]
    a = [1.0 + alpha, -2.0 * c, 1.0 - alpha]
    return _norm(b, a)


def _norm(b, a):
    return dict(b0=b[0] / a[0], b1=b[1] / a[0], b2=b[2] / a[0],
                a1=a[1] / a[0], a2=a[2] / a[0])


def resp_db(sec, f):
    w = 2.0 * math.pi * f / FS
    z1 = np.exp(-1j * w)
    z2 = z1 * z1
    num = sec["b0"] + sec["b1"] * z1 + sec["b2"] * z2
    den = 1.0 + sec["a1"] * z1 + sec["a2"] * z2
    return 20.0 * math.log10(abs(num / den) + 1e-30)


def cascade_db(secs, f):
    return sum(resp_db(s, f) for s in secs)


def to_q(x):
    return max(COEF_MIN, min(COEF_MAX, int(round(x * SCALE))))


def main():
    os.makedirs(OUT, exist_ok=True)
    chain = [("notch50", notch(50.0, 10.0)), ("lp40", lowpass(40.0, 0.707))]

    print("=" * 80)
    print("D4/D5 滤波链（最终方案）  fs=%.0fHz   Q2.14 定点" % FS)
    print("  级1 陷波 50Hz (Q=10)  →  级2 低通 40Hz (Q=0.707)")
    print("=" * 80)

    print("\n[1] 系数（浮点 → Q2.14）")
    coef_json = {"fs": FS, "frac": FRAC, "sections": []}
    secs_q = []
    for name, sec in chain:
        print("  --- %s ---" % name)
        entry, sq = {"name": name}, {}
        for k in ("b0", "b1", "b2", "a1", "a2"):
            q = to_q(sec[k])
            entry[k] = sq[k] = q
            print("    %-3s float=%11.8f  Q2.14=%6d (0x%04X)" % (k, sec[k], q, q & 0xFFFF))
        coef_json["sections"].append(entry)
        secs_q.append(sq)

    print("\n[2] 频响（两级级联）")
    print("    %8s %10s %10s" % ("频率Hz", "设计dB", "定点dB"))
    for f in (0.1, 0.5, 1, 2, 5, 10, 15, 20, 30, 40, 45, 48, 49.5, 50, 50.5, 51, 55, 60, 80, 100):
        qd = sum(resp_db({k: s[k] / SCALE for k in ("b0", "b1", "b2", "a1", "a2")}, f)
                 for s in secs_q)
        print("    %8.1f %10.2f %10.2f" % (f, cascade_db([s for _, s in chain], f), qd))

    g = lambda f: sum(resp_db({k: s[k] / SCALE for k in ("b0", "b1", "b2", "a1", "a2")}, f)
                      for s in secs_q)
    nsec = chain[0][1]
    lo = 50.0
    while resp_db(nsec, lo) < -3.0 and lo > 40.0:
        lo -= 0.01
    hi = 50.0
    while resp_db(nsec, hi) < -3.0 and hi < 60.0:
        hi += 0.01

    print("\n[3] 关键指标（定点系数）")
    print("    50Hz 抑制        : %.1f dB" % g(50.0))
    print("    陷波 -3dB 带宽   : %.2f ~ %.2f Hz（宽 %.2f Hz）" % (lo, hi, hi - lo))
    print("    49.5 / 50.5 / 51 Hz 抑制: %.1f / %.1f / %.1f dB" % (g(49.5), g(50.5), g(51.0)))
    print("    40Hz（截止点）   : %.2f dB（设计 -3dB）" % g(40.0))
    print("    5 / 15 Hz 增益   : %.2f / %.2f dB" % (g(5), g(15)))
    print("    通带 2~30Hz 起伏 : ±%.2f dB"
          % max(abs(g(f) - g(5)) for f in (2, 5, 10, 15, 20, 30)))

    print("\n[4] 稳定性（极点半径 <1）")
    for name, sec in chain:
        a1, a2 = sec["a1"], sec["a2"]
        disc = complex(a1 * a1 - 4 * a2) ** 0.5
        print("    %-8s %.6f, %.6f" % (name, abs((-a1 + disc) / 2), abs((-a1 - disc) / 2)))

    print("\n[5] 附：数字高通为什么被否决（评估记录）")
    hp = highpass(0.5, 0.707)
    A1 = 1.0 + hp["a1"] + hp["a2"]
    print("    0.5Hz 二阶高通：a1=%.6f a2=%.6f" % (hp["a1"], hp["a2"]))
    print("    A(1) = 1+a1+a2 = %.3e  →  量化误差放大 1/A(1) ≈ %.0f 倍" % (A1, 1 / A1))
    print("    16 位定点实测误差（判据 2 LSB）：")
    print("      截断 16 位        : 最大 3198 LSB（发散了）")
    print("      四舍五入 16 位    : 最大  729 LSB")
    print("      内部 Q14 高精度   : 最大   17 LSB（乘法器需 26 位，DSP 翻倍）")
    print("      一阶 DC 阻断(16位): 最大  140 LSB")
    print("    → 结论：结构性问题，改由 AD8232 硬件高通 + PT 内部带通 + PS 软件承担")

    coef_json["att50_db"] = g(50.0)
    coef_json["rejected_hp"] = {k: hp[k] for k in ("b0", "b1", "b2", "a1", "a2")}
    path = os.path.join(OUT, "filt_coef.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(coef_json, f, ensure_ascii=False, indent=1)
    print("\n已写出: %s" % path)


if __name__ == "__main__":
    main()