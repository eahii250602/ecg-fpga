#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pan_tompkins.py —— Pan-Tompkins 离线黄金参考（D2 上午）

【这是什么】Pan-Tompkins 是医学界最经典的"自适应"R 波检测法，五步：
    1) 带通滤波 5~15Hz    —— 只留 R 波主频，压掉基线漂移(<0.5Hz)和工频(50Hz)
    2) 五点微分           —— 尖峰更突出
    3) 平方               —— 全部变正，强调大斜率
    4) 滑动窗口积分(150ms) —— 把 QRS 包成一个"能量包"
    5) 自适应双阈值        —— 阈值随波形自动调整，不用手调 1200

【本脚本做什么】
    1) 用 DDS 的 256 点 ROM 模板 + 相位逻辑，生成与板上一致的 250Hz 心电
       （FTW=52 → 72.6BPM，每拍 206.49 个采样点）
    2) 造一个"真实世界"版本：加 50Hz 工频 + 0.3Hz 基线漂移 + 高斯噪声
    3) 黄金参考（真值）：直接取"干净信号上的 R 峰"——分析式、零误差
    4) 分别跑：① 旧固定阈值检测器 ② Pan-Tompkins，与真值对账
       —— 旧检测器在噪声下多检出 2 拍（22 vs 20），验证"为什么要换 PT"
    5) 输出 golden_rpeaks.csv 供 RTL 实现逐拍对账

【输出】out/ 目录
    golden_rpeaks.csv       真值 R 峰（干净信号上的 R 峰，标准答案）
    golden_rpeaks_pt.csv    PT 在噪声信号上的检测结果（与真值对照用）
    pt_input.hex            噪声信号（12 位补码）→ 以后 RTL 测试台专用
    pt_input_clean.hex      干净信号 → 同上
    summary.json            统计数字
    waveform.png            噪声波形 + PT 检测标记图（Pillow 画）
"""
import os
import sys
import json

import numpy as np
from PIL import Image, ImageDraw

FS        = 250.0        # 采样率
TICK_DIV  = 400000       # tick_gen 分频（100MHz / 400000 = 250Hz）
FTW       = 52           # → 72.6 BPM
NSAMP     = 4096         # 16.4 s
ROM_BASE  = 2048         # 偏移二进制基线
TOL       = 3            # 对账容差（采样点）

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "out")


def load_rom(path):
    vals = []
    with open(path, "r", encoding="ascii") as f:
        for line in f:
            line = line.strip()
            if line:
                vals.append(int(line, 16))
    return np.array(vals, dtype=np.int64)


def dds_wave(rom, ftw=FTW, n=NSAMP):
    """与 RTL 完全一致的 DDS 播放：相位每 tick 前进 TICK_DIV*FTW，取高 8 位查表"""
    k = np.arange(n)
    ph = (k * TICK_DIV * ftw) % (1 << 32)
    addr = ph >> 24
    return rom[addr] - ROM_BASE


def lp_coef(fc, ntap):
    n = np.arange(ntap)
    m = n - (ntap - 1) / 2.0
    return 2.0 * fc / FS * np.sinc(2.0 * fc / FS * m) * np.hamming(ntap)


def bandpass_coef(f_lo, f_hi, ntap):
    return lp_coef(f_hi, ntap) - lp_coef(f_lo, ntap)


def causal_fir(x, h):
    """因果 FIR（与 RTL 实现同构：y[n] = Σ h[k]x[n-k]）"""
    return np.convolve(x, h)[:len(x)]


def derivative5(x):
    d = np.zeros_like(x)
    d[4:] = (2.0 * x[4:] + x[3:-1] - x[1:-3] - 2.0 * x[:-4]) / 8.0
    return d


def moving_avg(x, w):
    c = np.concatenate(([0.0], np.cumsum(x)))
    y = np.zeros_like(x)
    y[w - 1:] = (c[w:] - c[:-w]) / float(w)
    return y


def local_maxima(y, min_dist=50):
    """局部极大值候选，强制最小间距 min_dist（200ms）"""
    idx = np.where((y[1:-1] >= y[:-2]) & (y[1:-1] > y[2:]))[0] + 1
    cand = []
    for i in idx:
        if not cand or i - cand[-1] >= min_dist:
            cand.append(i)
        elif y[i] > y[cand[-1]]:
            cand[-1] = i
    return np.array(cand, dtype=int)


def analytic_peaks(x, th=1500, min_dist=50):
    """真值：干净信号上的 R 峰（x > 1500 的局部极大，最小间距 200ms）"""
    idx = np.where((x[1:-1] >= x[:-2]) & (x[1:-1] > x[2:]) & (x[1:-1] > th))[0] + 1
    peaks = []
    for i in idx:
        if not peaks or i - peaks[-1] >= min_dist:
            peaks.append(i)
    return np.array(peaks, dtype=int)


def detect_pt(x):
    """Pan-Tompkins 检测器，返回 R 峰在原始信号上的采样序号"""
    h = bandpass_coef(5.0, 15.0, 61)
    xf = causal_fir(x, h)          # 1) 带通
    d = derivative5(xf)            # 2) 微分
    sq = d * d                     # 3) 平方
    integ = moving_avg(sq, 38)     # 4) 150ms 积分

    cand = local_maxima(integ, min_dist=50)
    if len(cand) == 0:
        return np.array([], dtype=int)

    # 5) 自适应双阈值（经典 PT 更新规则）
    peak_max = float(integ[cand].max())
    spki = 0.6 * peak_max          # 信号峰均值估计
    npki = 0.2 * peak_max          # 噪声峰均值估计
    r = []
    rr_avg = 0.0
    for c in cand:
        th1 = npki + 0.25 * (spki - npki)
        if integ[c] <= th1:
            npki = 0.125 * integ[c] + 0.875 * npki
            continue
        if r and (c - r[-1]) < 50:      # 200ms 不响应
            continue
        # 漏检回退：RR 超过 1.66 倍平均时，在空隙里找次强峰
        if r and rr_avg > 0:
            gap = c - r[-1]
            if gap > 1.66 * rr_avg:
                lo, hi = r[-1] + 50, c - 25
                if hi > lo:
                    j = lo + int(np.argmax(integ[lo:hi]))
                    if integ[j] > 0.5 * th1:
                        r.append(j)
                        rr_avg = 0.875 * rr_avg + 0.125 * (j - r[-2])
        r.append(c)
        spki = 0.125 * integ[c] + 0.875 * spki
        if len(r) >= 2:
            rr = r[-1] - r[-2]
            rr_avg = 0.875 * rr_avg + 0.125 * rr if rr_avg else float(rr)

    r = np.array(r, dtype=int)
    if len(r) == 0:
        return r

    # 峰值细化：在带通信号 xf 上找 QRS 峰，再减掉 30 采样固定延迟
    #   （带通 61 抽头线性相位，群延迟 = (61-1)/2 = 30）
    refined = []
    for c in r:
        lo, hi = max(0, c - 40), min(len(x), c + 41)
        p = lo + int(np.argmax(xf[lo:hi])) - 30
        refined.append(max(0, p))
    return np.array(sorted(set(refined)), dtype=int)


def detect_fixed(x, th=1200, blank=50):
    """旧版固定阈值检测器（对照用）：x > 1200 且 200ms 内只认一次"""
    r = []
    last = -10 ** 9
    for n, v in enumerate(x):
        if v > th and n - last >= blank:
            r.append(n)
            last = n
    return np.array(r, dtype=int)


def match(golden, rtl, tol):
    used = [False] * len(rtl)
    hit = 0
    for g in golden:
        best, bd = -1, tol + 1
        for i, rr in enumerate(rtl):
            if used[i]:
                continue
            d = abs(rr - g)
            if d <= tol and d < bd:
                best, bd = i, d
        if best >= 0:
            used[best] = True
            hit += 1
    return hit


def write_csv(path, rp, x):
    with open(path, "w", encoding="ascii") as f:
        f.write("index,time_s,raw\n")
        for i in rp:
            f.write("%d,%.4f,%d\n" % (int(i), i / FS, int(x[i])))


def write_hex(path, x):
    """12 位有符号（补码）hex，每行一个 —— 供 RTL 测试台 $readmemh"""
    with open(path, "w", encoding="ascii") as f:
        for v in x:
            f.write("%03X\n" % (int(v) & 0xFFF))


def draw_png(path, x, rp, title):
    """Pillow 画波形 + R 峰标记（无需 matplotlib）"""
    W, H = 900, 340
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    n = len(x)
    xmin, xmax = float(x.min()), float(x.max())
    span = max(1.0, xmax - xmin)
    def X(i): return 20 + int(i * (W - 40) / max(1, n - 1))
    def Y(v): return H - 20 - int((v - xmin) * (H - 40) / span)
    pts = [(X(i), Y(float(x[i]))) for i in range(0, n, 2)]
    d.line(pts, fill=(30, 30, 30), width=1)
    for i in rp:
        d.line([(X(int(i)), 15), (X(int(i)), H - 15)], fill=(220, 30, 30), width=2)
    d.text((10, 5), title, fill=(0, 0, 0))
    img.save(path)


def find_rom():
    r"""按常见位置找 256 点波形模板（工作区/D:\ecg 两处都试）"""
    cands = [
        os.path.join(HERE, "..", "..", "python", "ecg_256x12.mem"),   # D:\ecg\sim\pt_golden
        os.path.join(HERE, "..", "..", "ecg", "python", "ecg_256x12.mem"),  # 工作区布局
        r"D:\ecg\python\ecg_256x12.mem",
        os.path.join(HERE, "ecg_256x12.mem"),
    ]
    for c in cands:
        c = os.path.abspath(c)
        if os.path.isfile(c):
            return c
    raise SystemExit("找不到 ecg_256x12.mem，试过:\n  " + "\n  ".join(cands))


def main():
    os.makedirs(OUT, exist_ok=True)

    rom = load_rom(find_rom())
    clean = dds_wave(rom)

    # ---- 真实世界版本：50Hz 工频 + 0.3Hz 基线漂移 + 高斯噪声 ----
    rng = np.random.default_rng(20261026)
    t = np.arange(NSAMP) / FS
    noisy = (clean
             + 400.0 * np.sin(2 * np.pi * 50.0 * t)
             + 300.0 * np.sin(2 * np.pi * 0.3 * t)
             + rng.normal(0.0, 100.0, NSAMP))
    noisy = np.clip(np.round(noisy), -2048, 2047).astype(np.int64)

    # ---- 真值（干净信号上的 R 峰）与各检测器 ----
    golden = analytic_peaks(clean)
    rp_pt = detect_pt(noisy)
    rp_pt_clean = detect_pt(clean)
    fp_clean = detect_fixed(clean)
    fp_noisy = detect_fixed(noisy)

    # ---- 对账 ----
    hit = match(golden, rp_pt, TOL)
    hit_clean = match(golden, rp_pt_clean, TOL)
    rate = 100.0 * hit / max(1, len(golden))
    rate_clean = 100.0 * hit_clean / max(1, len(golden))

    # ---- 输出 ----
    write_csv(os.path.join(OUT, "golden_rpeaks.csv"), golden, clean)
    write_csv(os.path.join(OUT, "golden_rpeaks_pt.csv"), rp_pt, noisy)
    write_hex(os.path.join(OUT, "pt_input.hex"), noisy)
    write_hex(os.path.join(OUT, "pt_input_clean.hex"), clean)
    draw_png(os.path.join(OUT, "waveform.png"), noisy, rp_pt,
             "noisy DDS waveform (50Hz + drift + gauss) with PT R-peaks (red)")

    theory_rr = (1 << 32) / (FTW * TICK_DIV)
    golden_rr = np.diff(golden)

    summary = {
        "theory_rr_samples": theory_rr,
        "golden": {
            "beats": int(len(golden)),
            "rr_intervals": [int(v) for v in golden_rr],
            "rr_mean": float(golden_rr.mean()),
        },
        "pt_noisy": {
            "beats": int(len(rp_pt)),
            "rr_intervals": [int(v) for v in np.diff(rp_pt)],
            "match_vs_golden_tol3": int(hit),
            "match_rate_pct": float(rate),
        },
        "pt_clean": {
            "beats": int(len(rp_pt_clean)),
            "match_vs_golden_tol3": int(hit_clean),
            "match_rate_pct": float(rate_clean),
        },
        "fixed_threshold": {
            "clean_detections": int(len(fp_clean)),
            "noisy_detections": int(len(fp_noisy)),
            "note": "旧检测器在噪声下多检出 %d 拍（误检）" % (len(fp_noisy) - len(golden)),
        },
    }
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("理论每拍采样数 = %.2f" % theory_rr)
    print("真值（干净信号 R 峰）: %d 拍, 间隔: %s"
          % (len(golden), " ".join(str(v) for v in golden_rr)))
    print("PT @ 噪声信号       : %d 拍, 间隔: %s"
          % (len(rp_pt), " ".join(str(v) for v in np.diff(rp_pt).astype(int))))
    print("  与真值对照(±%d)   : %d/%d = %.1f%%" % (TOL, hit, len(golden), rate))
    print("PT @ 干净信号       : %d 拍, 与真值 %d/%d = %.1f%%"
          % (len(rp_pt_clean), hit_clean, len(golden), rate_clean))
    print("旧固定阈值检测器    : 干净 %d 拍 / 噪声 %d 拍（真值 %d 拍）→ 噪声下误检 %d 拍"
          % (len(fp_clean), len(fp_noisy), len(golden), len(fp_noisy) - len(golden)))
    print("输出目录:", OUT)


if __name__ == "__main__":
    main()
