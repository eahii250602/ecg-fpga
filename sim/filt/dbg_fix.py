import json, math, sys
import filt_fixed_sim as S

xs = S.make_input()
secs_f = [S.notch(50.0,10.0), S.highpass(0.5,0.707), S.lowpass(40.0,0.707)]
yf = S.run_float(xs, secs_f)

def q16(v): return int(round(v*16384))
alpha = math.exp(-2*math.pi*0.5/250.0)   # 一阶 DC blocker 系数

def run(mode, use_1st_order):
    # 级配置
    cj = json.load(open("out/filt_coef.json", encoding="utf-8"))["sections"]
    chain = []
    chain.append(dict(type="bq", c=cj[0]))                      # notch
    if use_1st_order:
        chain.append(dict(type="dc1", a=q16(alpha)))
    else:
        chain.append(dict(type="bq", c=cj[1]))                  # hp
    chain.append(dict(type="bq", c=cj[2]))                      # lp
    st = [dict(x1=0, x2=0, y1=0, y2=0, w1=0, w2=0) for _ in chain]
    ys = []
    for x0 in xs:
        v = x0
        for i, stg in enumerate(chain):
            s = st[i]
            if stg["type"] == "dc1":
                a = stg["a"]
                acc = (v - s["x1"]) * 16384 + a * s["y1"]      # v - x1 + alpha*y1
                y = (acc + 8192) >> 14 if mode.startswith("round") else acc >> 14
                s["x1"] = v; s["y1"] = y
            else:
                c = stg["c"]
                acc = (c["b0"]*v + c["b1"]*s["x1"] + c["b2"]*s["x2"]
                       - c["a1"]*s["y1"] - c["a2"]*s["y2"])
                y = (acc + 8192) >> 14 if mode.startswith("round") else acc >> 14
                s["x2"], s["x1"] = s["x1"], v
                s["y2"], s["y1"] = s["y1"], y
            if mode.endswith("16"):
                y = max(-32768, min(32767, y))
            v = y
        ys.append(max(-2048, min(2047, v)))
    return ys

for u1 in (False, True):
    for mode in ("trunc16", "round16", "round24"):
        ys = run(mode, u1)
        d = [abs(ys[i]-yf[i]) for i in range(500, 2000)]
        mx = max(d); mean = sum(d)/len(d)
        print("%-9s %-8s  最大误差=%7.1f  平均=%7.2f  输出范围=[%5d,%5d]"
              % ("1阶DC" if u1 else "2阶HP", mode, mx, mean, min(ys), max(ys)))
