# -*- coding: utf-8 -*-
"""生成技术文档所需的 5 张系统框图（A1~A5）"""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\ecg\report\figs"
os.makedirs(OUT, exist_ok=True)
F = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"

BG = (252, 252, 250)
INK = (30, 34, 40)
GREY = (110, 118, 128)
LINE = (150, 158, 168)
BLUE = (42, 96, 153)
LBLUE = (226, 237, 247)
GREEN = (36, 128, 84)
LGREEN = (224, 242, 233)
ORANGE = (176, 108, 24)
LORANGE = (250, 238, 218)
PURPLE = (108, 70, 148)
LPURPLE = (236, 230, 245)
RED = (176, 52, 52)
LRED = (250, 228, 228)


def font(sz, bold=False):
    return ImageFont.truetype(FB if bold else F, sz)


def canvas(w, h, title, sub=""):
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.text((w // 2, 26), title, font=font(32, True), fill=INK, anchor="ma")
    if sub:
        d.text((w // 2, 70), sub, font=font(18), fill=GREY, anchor="ma")
    return img, d


def box(d, x, y, w, h, text, fill, edge, tcol=None, fs=20, bold=True, sub=None):
    d.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=fill, outline=edge, width=2)
    d.text((x + w // 2, y + h // 2 - (10 if sub else 0)), text,
           font=font(fs, bold), fill=tcol or edge, anchor="mm")
    if sub:
        d.text((x + w // 2, y + h // 2 + 18), sub, font=font(14), fill=GREY, anchor="mm")


def arrow(d, x1, y1, x2, y2, col=LINE, wd=2):
    d.line([x1, y1, x2, y2], fill=col, width=wd)
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    L, S = 10, 0.45
    d.polygon([(x2, y2),
               (x2 - L * math.cos(a - S), y2 - L * math.sin(a - S)),
               (x2 - L * math.cos(a + S), y2 - L * math.sin(a + S))], fill=col)


# ============================================================
# A1 六层系统架构图
# ============================================================
W, H = 1680, 980
img, d = canvas(W, H, "图 A1　系统六层架构",
                "自下而上：采集 → 处理 → 传输 → 系统 → 智能；自检层为前五层提供可控激励")
layers = [
    ("⑥ 自检层", "DDS 可编程波形源　·　50 Hz 工频注入器　·　主机样本通道", LORANGE, ORANGE),
    ("⑤ 智能层", "心率 HR　·　心率变异性 HRV　·　呼吸率 EDR　·　心律规整性判读", LPURPLE, PURPLE),
    ("④ 系统层", "PYNQ Linux / Python：寄存器配置、波形回读、参数计算、实时显示", LGREEN, GREEN),
    ("③ 传输层", "波形缓冲 1024×32 BRAM　·　AXI-Stream 主口　·　AXI DMA (S2MM) → DDR", LBLUE, BLUE),
    ("② 处理层", "50 Hz 陷波 → 40 Hz 低通 → Pan-Tompkins 检测 → SQI / HRV 统计", LRED, RED),
    ("① 采集层", "模拟前端 → 分压网络 (2.7 kΩ / 0.93 kΩ) → 片上 XADC (12 位, 1 MSPS)", LBLUE, BLUE),
]
y = 130
bh = 108
gap = 26
for name, desc, fill, edge in layers:
    d.rounded_rectangle([120, y, W - 120, y + bh], radius=10, fill=fill, outline=edge, width=3)
    d.text((150, y + bh // 2 - 16), name, font=font(26, True), fill=edge, anchor="lm")
    d.text((150, y + bh // 2 + 18), desc, font=font(17), fill=(60, 66, 74), anchor="lm")
    y += bh + gap
# 层间箭头（左侧）
for i in range(len(layers) - 1):
    y1 = 130 + i * (bh + gap) + bh
    arrow(d, 96, y1 + 4, 96, y1 + gap - 4, col=GREY, wd=3)
# 自检层指向处理层（右侧）
d.line([W - 120, 130 + bh // 2, W - 66, 130 + bh // 2], fill=ORANGE, width=3)
d.line([W - 66, 130 + bh // 2, W - 66, 130 + 4 * (bh + gap) + bh // 2], fill=ORANGE, width=3)
arrow(d, W - 66, 130 + 4 * (bh + gap) + bh // 2, W - 120, 130 + 4 * (bh + gap) + bh // 2,
      col=ORANGE, wd=3)
d.text((W - 74, 130 + 2 * (bh + gap) + bh // 2), "激励注入", font=font(16, True),
       fill=ORANGE, anchor="rm")
img.save(os.path.join(OUT, "figA1_arch.png"))
print("A1 OK")

# ============================================================
# A2 RTL 数据流图
# ============================================================
W, H = 1740, 760
img, d = canvas(W, H, "图 A2　PL 内部数据流",
                "三路激励共用同一条滤波链，输出同时进入波形缓冲与 AXI-Stream")
# 第一行：三种信号源
box(d, 70, 150, 210, 84, "DDS 波形源", LORANGE, ORANGE, sub="相位累加 + 256 点 ROM", fs=22)
box(d, 70, 300, 210, 84, "50 Hz 注入器", LORANGE, ORANGE, sub="3 级流水 · 幅值可编程", fs=22)
box(d, 70, 450, 210, 84, "主机样本通道", LORANGE, ORANGE, sub="PS 写 0x00", fs=22)
# 选择器
box(d, 340, 290, 170, 104, "样本选择器", LBLUE, BLUE, sub="0x10 bit3", fs=22)
for yy in (192, 342, 492):
    arrow(d, 280, yy, 340, 342 if yy != 342 else 342, col=GREY)
# 滤波链
box(d, 570, 290, 200, 104, "两级 IIR 滤波", LRED, RED, sub="陷波 50 + 低通 40 · Q2.14", fs=22)
arrow(d, 510, 342, 570, 342, col=GREY)
# PT 检测
box(d, 830, 170, 190, 100, "PT 检测器", LPURPLE, PURPLE, sub="自适应双阈值 + T波判别", fs=22)
arrow(d, 770, 320, 830, 220, col=GREY)
# SQI / HRV
box(d, 830, 320, 190, 78, "SQI 质量评估", LGREEN, GREEN, sub="能量比 · 4 级", fs=20)
box(d, 830, 430, 190, 78, "HRV 累加器", LGREEN, GREEN, sub="n/Σrr/Σrr²/ΣΔrr²", fs=20)
arrow(d, 770, 360, 830, 359, col=GREY)
arrow(d, 770, 375, 830, 469, col=GREY)
# 输出
box(d, 1090, 170, 200, 100, "波形缓冲", LBLUE, BLUE, sub="1024×32 BRAM", fs=22)
arrow(d, 770, 342, 1090, 220, col=GREY)
box(d, 1090, 320, 200, 84, "虚拟寄存器", LBLUE, BLUE, sub="0x04 bit10 选通", fs=22)
arrow(d, 1020, 350, 1090, 360, col=GREY)
box(d, 1360, 150, 190, 96, "AXI4-Lite", LGREEN, GREEN, sub="寄存器 + 波形回读", fs=22)
arrow(d, 1290, 210, 1360, 198, col=GREY)
box(d, 1360, 320, 190, 96, "AXI-Stream", LGREEN, GREEN, sub="16 位 · 250 S/s", fs=22)
arrow(d, 1290, 210, 1360, 360, col=GREY)
box(d, 1600, 320, 110, 96, "AXI\nDMA", LORANGE, ORANGE, fs=20)
arrow(d, 1550, 368, 1600, 368, col=GREY)
d.text((W - 60, 450), "→ DDR 环形缓冲", font=font(18, True), fill=ORANGE, anchor="rm")
img.save(os.path.join(OUT, "figA2_rtl.png"))
print("A2 OK")

# ============================================================
# A3 分压网络电路图
# ============================================================
W, H = 1200, 680
img, d = canvas(W, H, "图 A3　XADC 输入分压网络",
                "将模拟前端 0~3.3 V 输出映射至 XADC 的 0~1.0 V 量程（分压比 0.2562）")
# 输入
d.text((90, 250), "模拟前端 OUT", font=font(20, True), fill=INK, anchor="lm")
d.text((90, 282), "0 ~ 3.3 V", font=font(17), fill=GREY, anchor="lm")
arrow(d, 250, 262, 340, 262, col=INK, wd=3)
# 上臂电阻
d.rectangle([340, 232, 470, 292], fill=LORANGE, outline=ORANGE, width=3)
d.text((405, 262), "2.7 kΩ", font=font(20, True), fill=ORANGE, anchor="mm")
# 节点
arrow(d, 470, 262, 560, 262, col=INK, wd=3)
d.ellipse([550, 252, 570, 272], fill=INK)
d.text((560, 225), "V_div", font=font(19, True), fill=BLUE, anchor="mm")
# 输出到 VP
arrow(d, 570, 262, 700, 262, col=BLUE, wd=3)
d.text((710, 240), "J5 → VP", font=font(20, True), fill=BLUE, anchor="lm")
d.text((710, 272), "0 ~ 0.845 V", font=font(17), fill=GREY, anchor="lm")
d.text((710, 300), "（XADC 12 位量化）", font=font(16), fill=GREY, anchor="lm")
# 下臂电阻
d.line([560, 272, 560, 360], fill=INK, width=3)
d.rectangle([500, 360, 620, 420], fill=LORANGE, outline=ORANGE, width=3)
d.text((560, 390), "0.93 kΩ", font=font(20, True), fill=ORANGE, anchor="mm")
d.line([560, 420, 560, 500], fill=INK, width=3)
# 地
d.line([490, 500, 630, 500], fill=INK, width=4)
for i, wlx in enumerate([540, 560, 580]):
    d.line([wlx - (30 - i * 10), 516, wlx + (30 - i * 10), 516], fill=INK, width=3)
d.text((560, 545), "GND（J5）", font=font(19, True), fill=INK, anchor="mm")
# 说明框
d.rounded_rectangle([760, 400, 1140, 620], radius=8, fill=(255, 255, 255),
                    outline=LINE, width=2)
d.text((782, 418), "设计要点", font=font(20, True), fill=INK, anchor="lm")
notes = ["分压比 = 0.93/(2.7+0.93) = 0.2562",
         "3.3 V 输入 → 0.845 V，留 15% 余量",
         "XADC 单极性量程 0 ~ 1.0 V",
         "1 LSB = 1.0 V / 4096 = 0.244 mV"]
for i, n in enumerate(notes):
    d.text((782, 460 + i * 38), "· " + n, font=font(17), fill=(60, 66, 74), anchor="lm")
img.save(os.path.join(OUT, "figA3_divider.png"))
print("A3 OK")

# ============================================================
# A4 软件模块框图
# ============================================================
W, H = 1500, 760
img, d = canvas(W, H, "图 A4　PS 侧软件模块组成",
                "四类共 18 个脚本，围绕同一组寄存器接口组织")
groups = [
    ("配置与回读", LBLUE, BLUE, ["ecg_timebase.py", "regtest.py", "xadc_selftest.py"]),
    ("专项验收", LRED, RED, ["filt_check.py　(抑制比)", "host_ecg.py　(真实信号)",
                          "vitals_check.py　(SQI/HRV)", "dma_check.py　(DMA)"]),
    ("实时显示", LGREEN, GREEN, ["term_monitor.py　(串口波形)", "web_monitor.py　(网页版)"]),
    ("算法验证", LPURPLE, PURPLE, ["vitals.py　(三参数注入验证)", "perf_baseline.py　(性能基线)",
                               "rhythm_check.py　(心律判读)"]),
]
x = 60
bw = 330
for name, fill, edge, items in groups:
    d.rounded_rectangle([x, 130, x + bw, 640], radius=10, fill=fill, outline=edge, width=3)
    d.text((x + bw // 2, 168), name, font=font(24, True), fill=edge, anchor="mm")
    d.line([x + 24, 196, x + bw - 24, 196], fill=edge, width=2)
    yy = 232
    for it in items:
        d.text((x + 24, yy), "· " + it, font=font(16), fill=(50, 56, 64), anchor="lm")
        yy += 46
    x += bw + 26
# 底部统一接口层
d.rounded_rectangle([60, 672, W - 60, 730], radius=8, fill=(240, 242, 245),
                    outline=GREY, width=2)
d.text((W // 2, 701), "统一接口：mmio.write(0x04, addr)  →  mmio.read(0x0C)",
       font=font(20, True), fill=GREY, anchor="mm")
img.save(os.path.join(OUT, "figA4_sw.png"))
print("A4 OK")

# ============================================================
# A5 采集推送流程图
# ============================================================
W, H = 1080, 900
img, d = canvas(W, H, "图 A5　采集与推送流程",
                "以 perf_counter 忙等保证 250.00 Hz，样本经 0x00 写入硬件链")
steps = [
    ("开始", "设置 FTW、清控制字", LBLUE, BLUE),
    ("计算下一采样时刻", "t_next += 1/250", LGREEN, GREEN),
    ("忙等到 t_next", "while perf_counter() < t_next", LORANGE, ORANGE),
    ("读 XADC 通道 3", "code = (read(0x20C) >> 4) & 0xFFF", LRED, RED),
    ("写入硬件链", "mmio.write(0x00, code)", LPURPLE, PURPLE),
    ("样本计数 +1", "i += 1", LBLUE, BLUE),
]
y = 130
bw, bh = 620, 84
for i, (name, detail, fill, edge) in enumerate(steps):
    x = (W - bw) // 2
    d.rounded_rectangle([x, y, x + bw, y + bh], radius=8, fill=fill, outline=edge, width=2)
    d.text((x + bw // 2, y + 30), name, font=font(22, True), fill=edge, anchor="mm")
    d.text((x + bw // 2, y + 60), detail, font=font(16), fill=(70, 76, 84), anchor="mm")
    if i < len(steps) - 1:
        arrow(d, W // 2, y + bh, W // 2, y + bh + 28, col=GREY, wd=2)
    y += bh + 28
# 判断
d.polygon([(W // 2, y), (W // 2 + 130, y + 48), (W // 2, y + 96), (W // 2 - 130, y + 48)],
          fill=LGREEN, outline=GREEN)
d.text((W // 2, y + 48), "i < N ?", font=font(20, True), fill=GREEN, anchor="mm")
arrow(d, W // 2 - 130, y + 48, 150, y + 48, col=GREEN, wd=2)
d.line([150, y + 48, 150, 172], fill=GREEN, width=2)
arrow(d, 150, 172, (W - bw) // 2, 172, col=GREEN, wd=2)
d.text((170, y + 30), "是（循环）", font=font(16, True), fill=GREEN, anchor="lm")
d.text((W // 2 + 145, y + 48), "否 → 结束", font=font(17, True), fill=GREY, anchor="lm")
img.save(os.path.join(OUT, "figA5_flow.png"))
print("A5 OK")

print("\n输出目录:", OUT)
for f in ["figA1_arch.png", "figA2_rtl.png", "figA3_divider.png",
          "figA4_sw.png", "figA5_flow.png"]:
    p = os.path.join(OUT, f)
    print("  %-24s %7.1f KB" % (f, os.path.getsize(p) / 1024))
