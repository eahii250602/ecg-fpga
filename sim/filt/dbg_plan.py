import json, math
import filt_fixed_sim as S
xs = S.make_input()

def run_fixed(xs, secs_q, frac=14):
    st = [dict(x1=0,x2=0,y1=0,y2=0) for _ in secs_q]
    out = []
    for x0 in xs:
        v = x0
        for i, c in enumerate(secs_q):
            s = st[i]
            acc = (c["b0"]*v + c["b1"]*s["x1"] + c["b2"]*s["x2"]
                   - c["a1"]*s["y1"] - c["a2"]*s["y2"])
            y = (acc + (1 << (frac-1))) >> frac          # 四舍五入
            y = max(-32768, min(32767, y))
            s["x2"], s["x1"] = s["x1"], v
            s["y2"], s["y1"] = s["y1"], y
            v = y
        out.append(max(-2048, min(2047, v)))
    return out

cj = json.load(open("out/filt_coef.json", encoding="utf-8"))["sections"]
notch, hp, lp = cj[0], cj[1], cj[2]

# 方案 A：陷波 + 低通（去掉数字高通）
secsA = [notch, lp]
refA = [S.notch(50.0,10.0), S.lowpass(40.0,0.707)]
yfA = S.run_float(xs, refA); yqA = run_fixed(xs, secsA)
dA = [abs(yqA[i]-yfA[i]) for i in range(500,2000)]
print("方案A 陷波+低通        : 最大误差=%6.1f  平均=%6.2f  max|y|=%d" % (max(dA), sum(dA)/len(dA), max(abs(v) for v in yqA)))

# 方案 B：陷波 + 高通 + 低通，但内部保持 Q14 精度（不每级截断）
def run_wide(xs, secs_q):
    Q = 14
    st = [dict(x1=0,x2=0,y1=0,y2=0) for _ in secs_q]
    out = []
    for x0 in xs:
        v = x0 << Q                     # 输入变 Q14
        for i, c in enumerate(secs_q):
            s = st[i]
            acc = (c["b0"]*v + c["b1"]*s["x1"] + c["b2"]*s["x2"]
                   - c["a1"]*s["y1"] - c["a2"]*s["y2"])
            y = (acc + (1 << (Q-1))) >> Q     # 结果仍是 Q14，不降到 Q0
            s["x2"], s["x1"] = s["x1"], v
            s["y2"], s["y1"] = s["y1"], y
            v = y
        out.append(max(-2048, min(2047, v >> Q)))
    return out
yfB = S.run_float(xs, [S.notch(50.0,10.0), S.highpass(0.5,0.707), S.lowpass(40.0,0.707)])
yqB = run_wide(xs, cj)
dB = [abs(yqB[i]-yfB[i]) for i in range(500,2000)]
print("方案B 三级+内部Q14精度 : 最大误差=%6.1f  平均=%6.2f  max|y|=%d" % (max(dB), sum(dB)/len(dB), max(abs(v) for v in yqB)))
