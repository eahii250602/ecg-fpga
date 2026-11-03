#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare_rpeaks.py —— R 峰对账工具（黄金参考 vs RTL 输出）

用法：
    python3 compare_rpeaks.py golden_rpeaks.csv rtl_rpeaks.csv [容差=2]

两个文件格式（CSV，第一列是采样序号，列名 index 或其他都可）：
    index,time_s,raw      ← golden（本目录 golden_rpeaks.csv）
    <各种格式>           ← RTL 输出（第一列序号即可）

判据（HANDOFF 7.2 D2）：重合 ≥95% 且容差 ±2 采样点。
"""
import sys
import csv


def read_indices(path):
    out = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.replace("\t", ",").split(",")
            p = parts[0].strip()
            try:
                out.append(int(p))
            except ValueError:
                continue   # 表头或非数字行跳过
    return out


def match(golden, rtl, tol):
    """贪心匹配：每个 golden 峰在 rtl 里找容差内未用过的最近峰"""
    used = [False] * len(rtl)
    hit = 0
    for g in golden:
        best, bd = -1, tol + 1
        for i, r in enumerate(rtl):
            if used[i]:
                continue
            d = abs(r - g)
            if d <= tol and d < bd:
                best, bd = i, d
        if best >= 0:
            used[best] = True
            hit += 1
    return hit


def main():
    if len(sys.argv) < 3:
        print("用法: python3 compare_rpeaks.py golden.csv rtl.csv [容差=2]")
        return 1
    tol = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    golden = read_indices(sys.argv[1])
    rtl = read_indices(sys.argv[2])

    hit = match(golden, rtl, tol)
    miss = len(golden) - hit
    extra = len(rtl) - hit
    rate = 100.0 * hit / max(1, len(golden))

    print("golden: %d 个峰, rtl: %d 个峰, 容差 ±%d" % (len(golden), len(rtl), tol))
    print("匹配: %d  漏检: %d  误检: %d  重合率: %.1f%%" % (hit, miss, extra, rate))
    if rate >= 95.0 and miss == 0 and extra == 0:
        print("结论: PASS")
        return 0
    print("结论: FAIL")
    return 2


if __name__ == "__main__":
    sys.exit(main())
