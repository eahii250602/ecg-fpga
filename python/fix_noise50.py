import math, re
lines = []
for k in range(256):
    v = int(round(1024.0 * math.sin(2.0 * math.pi * k / 256.0)))
    sign = "-" if v < 0 else ""
    lines.append("        sin_tab[%3d] = %s12'sd%d;" % (k, sign, abs(v)))
tab = "\n".join(lines)

p = r"D:\ecg\ip_repo\ecg_axi_1_0\hdl\noise50.v"
src = open(p, encoding="utf-8").read()
start = src.index("    initial begin")
end = src.index("    end", src.index("sin_tab[255]"))
new_body = "    initial begin\n" + tab + "\n    end"
src = src[:start] + new_body + src[end+len("    end"):]
open(p, "w", encoding="utf-8", newline="\n").write(src)
print("patched ok, table lines:", len(lines))
