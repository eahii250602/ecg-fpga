#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""filt_fixed_sim.py —— D4/D5 第 2 步：定点仿真（照 Verilog 的算法逐样本模拟）

最终方案：50Hz 陷波（2 阶）→ 40Hz 低通（2 阶），Direct Form I，Q2.14 系数。

定点规范（与将要写的 RTL 完全一致）：
  · 输入 x       : 12 位有符号（±2047），参与运算时符号扩展
  · 系数         : 16 位有符号 Q2.14
  · 状态 x1,x2,y1,y2 : 16 位（带饱和安全网）
  · 每级输出     : (b0*x + b1*x1 + b2*x2 - a1*y1 - a2*y2 + 8192) >>> 14
                   （+8192 = 四舍五入；截断会引入直流偏置，实测会发散）
  · 末级输出     : 饱和到 ±2047（12 位）

测试信号（N=2000 = 8 秒 @250Hz）：
  · 心电：DDS ROM 波形（FTW=83 → 206.99 点/拍，与板上一致），幅度 ×0.6
  · 50Hz 工频：600 LSB
  · 0.2Hz 基线漂移：300 LSB（PL 不处理，由 AD8232 硬件 + PT 带通 + PS 软件负责）

输出：out/filt_input.hex、out/filt_expected.txt（给第 4 步 RTL 对账用）
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design_iir import FS, FRAC, notch, lowpass          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ROM = r"D:\ecg\python\ecg_256x12.mem"

N = 2000
FTW = 83
TICK_DIV = 250000
NOISE50 = 600.0
DRIFT = 300.0
ECG_GAIN = 0.6


def load_rom():
    vals = []
    with open(ROM, "r", encoding="ascii") as f:
        for line in f:
            s = line.strip()
            if s:
                vals.append(int(s, 16))
    return vals


def make_input():
    rom = load_rom()
    step = TICK_DIV * FTW
    xs = []
    for n in range(N):
        addr = ((n * step) % (1 << 32)) >> 24
        ecg = (rom[addr] - 2048) * ECG_GAIN
        v = int(round(ecg
                      + NOISE50 * math.sin(2 * math.pi * 50.0 * n / FS)
                      + DRIFT * math.sin(2 * math.pi * 0.2 * n / FS)))
        xs.append(max(-2048, min(2047, v)))
    return xs


def run_float(xs, secs):
    st = [dict(x1=0.0, x2=0.0, y1=0.0, y2=0.0) for _ in secs]
    out = []
    for x0 in xs:
        v = float(x0)
        for i, c in enumerate(secs):
            s = st[i]
            y = (c["b0"] * v + c["b1"] * s["x1"] + c["b2"] * s["x2"]
                 - c["a1"] * s["y1"] - c["a2"] * s["y2"])
            s["x2"], s["x1"] = s["x1"], v
            s["y2"], s["y1"] = s["y1"], y
            v = y
        out.append(v)
    return out


def sat(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def run_fixed(xs, secs_q):
    st = [dict(x1=0, x2=0, y1=0, y2=0) for _ in secs_q]
    out = []
    for x0 in xs:
        v = x0
        for i, c in enumerate(secs_q):
            s = st[i]
            acc = (c["b0"] * v + c["b1"] * s["x1"] + c["b2"] * s["x2"]
                   - c["a1"] * s["y1"] - c["a2"] * s["y2"])
            y = (acc + (1 << (FRAC - 1))) >> FRAC        # 四舍五入（不是截断）
            y = sat(y, -32768, 32767)
            s["x2"], s["x1"] = s["x1"], v
            s["y2"], s["y1"] = s["y1"], y
            v = y
        out.append(sat(v, -2048, 2047))
    return out


def amp_at(f, xs):
    n = len(xs)
    k = 2.0 * math.pi * f / FS
    c = sum(xs[i] * math.cos(k * i) for i in range(n))
    s = sum(xs[i] * math.sin(k * i) for i in range(n))
    return 2.0 * math.hypot(c, s) / n


def sw_dc_block(xs):
    """PS 软件去基线（一阶高通，浮点）——PL 不做，这里演示软件侧能力"""
    alpha = math.exp(-2 * math.pi * 0.5 / FS)
    y = 0.0
    x1 = 0.0
    out = []
    for x0 in xs:
        y = x0 - x1 + alpha * y
        x1 = x0
        out.append(y)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "filt_coef.json"), "r", encoding="utf-8") as f:
        secs_q = json.load(f)["sections"]
    secs_f = [notch(50.0, 10.0), lowpass(40.0, 0.707)]

    xs = make_input()
    yf = run_float(xs, secs_f)
    yq = run_fixed(xs, secs_q)

    print("=" * 78)
    print("D4/D5 第 2 步：定点仿真   N=%d (%.1f s @%.0fHz)   陷波→低通" % (N, N / FS, FS))
    print("=" * 78)

    print("\n[1] 范围")
    print("    输入    : [%5d, %5d]" % (min(xs), max(xs)))
    print("    浮点输出: [%7.1f, %7.1f]" % (min(yf), max(yf)))
    print("    定点输出: [%5d, %5d]" % (min(yq), max(yq)))

    skip = 300
    d = [abs(yq[i] - yf[i]) for i in range(skip, N)]
    rms = math.sqrt(sum(x * x for x in d) / len(d))
    print("\n[2] 定点 vs 浮点（跳过前 %d 点启动瞬态）" % skip)
    print("    最大误差 = %6.2f LSB" % max(d))
    print("    平均误差 = %6.3f LSB" % (sum(d) / len(d)))
    print("    均方根   = %6.3f LSB  (满量程 4096 的 %.3f%%)" % (rms, rms / 4096 * 100))
    print("    判定: %s（判据 ≤2 LSB）" % ("PASS" if max(d) <= 2.0 else "FAIL"))

    print("\n[3] 实测效果")
    # (a) 纯 50Hz 测试：没有别的成分，测量最干净（2000 点 = 400 个整周期）
    SS = 500                       # 稳态起点（跳过启动瞬态，瞬态约 112 点）
    pure_in = [int(round(NOISE50 * math.sin(2 * math.pi * 50.0 * n / FS))) for n in range(N)]
    pure_out = run_fixed(pure_in, secs_q)
    a_pi = amp_at(50.0, pure_in[SS:])
    a_po = amp_at(50.0, pure_out[SS:])
    if a_po > 0.02:
        print("    (a) 纯 50Hz 稳态: %6.1f → %6.3f  → 抑制 %6.1f dB"
              % (a_pi, a_po, 20 * math.log10(a_po / a_pi)))
    else:
        print("    (a) 纯 50Hz 稳态: %6.1f → %.3f（低于 1 LSB，测不出）"
              % (a_pi, a_po))
        print("        → 稳态输出几乎为 0，抑制优于 %.0f dB（理论 -94.8dB）"
              % (20 * math.log10(0.5 / a_pi)))
    print("        （前 112 点是启动瞬态；稳态窗口 = 后 1500 点 = 300 个整周期）")

    # (b) 混合信号（ECG+50Hz+漂移）：会有频谱泄漏，数值偏保守
    a50i, a50o = amp_at(50.0, xs[SS:]), amp_at(50.0, yq[SS:])
    print("    (b) 混合信号稳态: %6.1f → %6.3f  → 测得 %6.1f dB"
          % (a50i, a50o, 20 * math.log10(max(a50o, 1e-9) / a50i)))
    print("        （含 0.2Hz 漂移与心电谐波的频谱泄漏，偏保守，仅作参考）")

    adi, ado = amp_at(0.2, xs), amp_at(0.2, yq)
    print("    0.2Hz 漂移: 输入 %7.1f → 输出 %6.1f（%+.1f dB，PL 不处理，属设计取舍）"
          % (adi, ado, 20 * math.log10(max(ado, 1e-9) / adi)))

    print("\n[4] 心电保真")
    pk_i = max(abs(v) for v in xs)
    pk_o = max(abs(v) for v in yq)
    print("    峰值: %d → %d（%.0f%%）" % (pk_i, pk_o, 100.0 * pk_o / pk_i))
    peaks = []
    for i in range(1, N - 1):
        if abs(yq[i]) > 700 and abs(yq[i]) >= abs(yq[i - 1]) and abs(yq[i]) > abs(yq[i + 1]):
            if not peaks or i - peaks[-1] > 100:
                peaks.append(i)
    print("    R 峰位置: %s" % peaks[:6])
    if len(peaks) > 1:
        print("    RR 间隔 : %s（期望 ~207）"
              % [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)][:6])

    print("\n[5] PS 软件去基线（PL 不做，软件侧演示）")
    ysw = sw_dc_block(yq)
    a02s = amp_at(0.2, ysw)
    print("    0.2Hz 漂移: 滤波后 %6.1f → 软件去基线后 %6.2f（%+.1f dB）"
          % (ado, a02s, 20 * math.log10(max(a02s, 1e-9) / max(ado, 1e-9))))

    with open(os.path.join(OUT, "filt_input.hex"), "w", encoding="ascii") as f:
        for v in xs:
            f.write("%03X\n" % (v & 0xFFF))
    with open(os.path.join(OUT, "filt_expected.txt"), "w", encoding="ascii") as f:
        for v in yq:
            f.write("%d\n" % v)
    print("\n[6] 已导出 out/filt_input.hex / out/filt_expected.txt（%d 点）" % N)

    print("\n[7] 前 10 点对照（输入 / 浮点 / 定点 / 差）")
    for i in range(10):
        print("    %3d %6d %8.2f %6d %6.1f" % (i, xs[i], yf[i], yq[i], yq[i] - yf[i]))


if __name__ == "__main__":
    main()