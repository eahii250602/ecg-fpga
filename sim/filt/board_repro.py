# -*- coding: utf-8 -*-
"""board_repro.py —— 用定点模型复现板上这次实验，给出理论答案"""
import json, math
import filt_fixed_sim as fs

fs.N = 1024
fs.NOISE50 = 600.0
fs.DRIFT = 0.0
fs.ECG_GAIN = 1.0
xs = fs.make_input()

secs_q = json.load(open("out/filt_coef.json", encoding="utf-8"))["sections"]
ys = fs.run_fixed(xs, secs_q)

def rep(name, v):
    print("  %-12s 50Hz=%7.2f LSB  范围=[%5d,%5d]  均值=%7.2f" %
          (name, fs.amp_at(50.0, v), min(v), max(v), sum(v)/len(v)))

print("=" * 66)
print("模型复现（输入与板上相同：心电 + 600LSB/50Hz）")
print("=" * 66)
rep("原始", xs)
rep("滤波后", ys)
a0 = fs.amp_at(50.0, xs); a1 = fs.amp_at(50.0, ys)
print("\n  理论抑制比 = %.1f dB" % (20*math.log10(a1/a0)))
print("  理论心电峰值保留 = %.0f%%" % (100.0*max(ys)/max(xs)))

pure = [int(round(600*math.sin(2*math.pi*50.0*n/250.0 + 0.7))) for n in range(1024)]
print("\n  对照：纯 600LSB 正弦 -> 测到 %.2f LSB（测量自检，应约 600）"
      % fs.amp_at(50.0, pure))
