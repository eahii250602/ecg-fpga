import json, math
import filt_fixed_sim as S
cj = json.load(open("out/filt_coef.json", encoding="utf-8"))
secs_q = cj["sections"]
xs = S.make_input()
# 逐级追踪：每级单独跑，看输出范围
for name, sec in zip(["notch", "hp", "lp"], secs_q):
    st = dict(x1=0, x2=0, y1=0, y2=0)
    mx = 0
    hdr = []
    for n, x0 in enumerate(xs[:400]):
        acc = (sec["b0"]*x0 + sec["b1"]*st["x1"] + sec["b2"]*st["x2"]
               - sec["a1"]*st["y1"] - sec["a2"]*st["y2"])
        y = acc >> 14
        st["x2"], st["x1"] = st["x1"], x0
        st["y2"], st["y1"] = st["y1"], y
        mx = max(mx, abs(y))
        if n < 6:
            hdr.append(y)
    print("%-6s 单独跑 前6个输出=%s  max|y|=%d" % (name, hdr, mx))
# 看浮点各级范围
sf = [S.notch(50.0,10.0), S.highpass(0.5,0.707), S.lowpass(40.0,0.707)]
for name, sec in zip(["notch", "hp", "lp"], sf):
    st = dict(x1=0.0, x2=0.0, y1=0.0, y2=0.0)
    mx = 0
    for x0 in xs[:1000]:
        y = (sec["b0"]*x0 + sec["b1"]*st["x1"] + sec["b2"]*st["x2"]
             - sec["a1"]*st["y1"] - sec["a2"]*st["y2"])
        st["x2"], st["x1"] = st["x1"], float(x0)
        st["y2"], st["y1"] = st["y1"], y
        mx = max(mx, abs(y))
    print("%-6s 浮点单独跑 max|y|=%.1f" % (name, mx))
