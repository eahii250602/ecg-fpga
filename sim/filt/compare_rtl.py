#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare_rtl.py —— 第 4 步对账：RTL 输出 vs Python 定点模型输出

判据：2000 个样本必须【逐位相同】。
若不同，先怀疑对齐（多/少算了一拍），所以自动扫 -3..+3 的样本偏移。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def read_ints(path):
    with open(path, "r", encoding="ascii") as f:
        return [int(x.strip()) for x in f if x.strip()]


def main():
    rtl = read_ints(os.path.join(OUT, "rtl_out.txt"))
    exp = read_ints(os.path.join(OUT, "filt_expected.txt"))

    print("=" * 70)
    print("第 4 步对账：RTL vs Python 定点模型")
    print("=" * 70)
    print("  RTL 样本数     : %d" % len(rtl))
    print("  期望样本数     : %d" % len(exp))

    n = min(len(rtl), len(exp))
    # 先按零偏移比
    bad = [i for i in range(n) if rtl[i] != exp[i]]
    print("\n[1] 零偏移比对")
    print("  不符个数       : %d / %d" % (len(bad), n))
    if bad:
        print("  前 10 个不符位置: %s" % bad[:10])

    # 再扫偏移，确认是不是"整体差了几拍"
    print("\n[2] 偏移扫描（看是不是整体错位）")
    best = None
    for s in range(-3, 4):
        same = 0
        tot = 0
        for i in range(n):
            j = i + s
            if 0 <= j < n:
                tot += 1
                if rtl[i] == exp[j]:
                    same += 1
        rate = same / tot if tot else 0
        tag = ""
        if best is None or rate > best[1]:
            best = (s, rate)
        print("  偏移 %+d : 相同 %5d / %5d = %6.2f%%%s"
              % (s, same, tot, rate * 100, tag))

    print("\n[3] 判定")
    if len(bad) == 0 and len(rtl) == len(exp):
        print("  ✅ PASS —— 2000 个样本逐位相同，RTL 与 Python 模型完全等价")
    else:
        print("  ❌ FAIL —— 需要排查")
        print("  最佳偏移 = %+d（相同率 %.2f%%）" % best)
        k = 0
        for i in range(n):
            if rtl[i] != exp[i]:
                print("    i=%4d  RTL=%6d  期望=%6d  差=%+d"
                      % (i, rtl[i], exp[i], rtl[i] - exp[i]))
                k += 1
                if k >= 12:
                    break

    # 统计一下误差分布（即使不完全相同也有参考价值）
    if bad:
        d = [rtl[i] - exp[i] for i in bad]
        print("\n  误差范围: %+d ~ %+d" % (min(d), max(d)))


if __name__ == "__main__":
    main()