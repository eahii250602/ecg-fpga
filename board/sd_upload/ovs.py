import time, numpy as np
from pynq import Overlay, MMIO
o = Overlay('/boot/ecg_bd.bit'); time.sleep(1)
m = MMIO(0x43C10000, 0x1000)
FS = 250.0

def band(x, lo, hi):
    n = len(x)
    sp = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(n))) / n * 2
    fr = np.fft.rfftfreq(n, 1 / FS)
    s = (fr >= lo) & (fr <= hi)
    return float(np.sqrt(np.mean(sp[s] ** 2)))

def cap(dur, os_n):
    n = int(dur * FS)
    out = np.empty(n)
    t = time.perf_counter()
    for i in range(n):
        if os_n == 1:
            v = (m.read(0x20C) >> 4) & 0xFFF
        else:
            a = 0
            for k in range(os_n):
                a += (m.read(0x20C) >> 4) & 0xFFF
            v = a / os_n
        out[i] = v
        t += 1.0 / FS
        while time.perf_counter() < t:
            pass
    return out

print("A: OS=1, 8s ...")
x1 = cap(8, 1)
s1 = band(x1, 5, 15); n1 = max(band(x1, 1, 4), band(x1, 20, 40))
print("  p2p=%d sig=%.2f noise=%.2f snr=%.2f" % (x1.max()-x1.min(), s1, n1, s1/max(n1,1e-9)))
print("B: OS=800, 8s ...")
x2 = cap(8, 800)
s2 = band(x2, 5, 15); n2 = max(band(x2, 1, 4), band(x2, 20, 40))
print("  p2p=%d sig=%.2f noise=%.2f snr=%.2f" % (x2.max()-x2.min(), s2, n2, s2/max(n2,1e-9)))
r1 = s1 / max(n1, 1e-9); r2 = s2 / max(n2, 1e-9)
print("GAIN = %+.1f dB" % (20 * np.log10(max(r2,1e-9) / max(r1,1e-9))))
np.save('/boot/ovs_x2.npy', x2)
print("saved /boot/ovs_x2.npy")
