import json, math
import filt_fixed_sim as S
cj = json.load(open("out/filt_coef.json", encoding="utf-8"))["sections"]
N = 2000
pin = [int(round(600*math.sin(2*math.pi*50.0*n/250.0))) for n in range(N)]
out = S.run_fixed(pin, cj)
def amp(xs):
    n=len(xs); k=2*math.pi*50.0/250.0
    c=sum(xs[i]*math.cos(k*i) for i in range(n)); s=sum(xs[i]*math.sin(k*i) for i in range(n))
    return 2*math.hypot(c,s)/n
print("前500点幅度  = %.3f"%amp(out[:500]))
print("中段500-1000= %.3f"%amp(out[500:1000]))
print("末段1500-2000=%.3f"%amp(out[1500:2000]))
print("尾部 20 个输出:", out[-20:])
print("输出非零个数 : %d / %d"%(sum(1 for v in out if v!=0), len(out)))
