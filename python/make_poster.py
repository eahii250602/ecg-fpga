# -*- coding: utf-8 -*-
"""生成作品海报（A3 竖版，深蓝系，白字），输出 PNG + PDF"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FIG = r"D:\ecg\report\figs"
OUT_PNG = r"D:\ecg\report\figs\poster.png"
OUT_PDF = r"D:\ecg\docs\心衡_作品海报.pdf"

W, H = 1754, 2480
F = r"C:\Windows\Fonts\msyh.ttc"
FB = r"C:\Windows\Fonts\msyhbd.ttc"

# 深蓝配色
C_BG1 = (8, 20, 38)
C_BG2 = (18, 40, 68)
C_CARD = (20, 44, 74)
C_CARD2 = (14, 33, 57)
C_EDGE = (46, 96, 150)
C_ACC = (77, 163, 255)
C_ACC2 = (127, 209, 255)
C_WHITE = (255, 255, 255)
C_DIM = (176, 200, 228)
C_GOLD = (255, 200, 90)


def fnt(sz, bold=False):
    return ImageFont.truetype(FB if bold else F, sz)


def grad_bg(w, h):
    top = np.array(C_BG1, dtype=float)
    bot = np.array(C_BG2, dtype=float)
    ramp = np.linspace(0, 1, h)[:, None]
    col = top[None, :] * (1 - ramp) + bot[None, :] * ramp
    arr = np.repeat(col[:, None, :], w, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


img = grad_bg(W, H)
d = ImageDraw.Draw(img)


def card(x, y, w, h, fill=C_CARD, edge=C_EDGE, r=18, width=2):
    d.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=fill, outline=edge, width=width)


def tex(xy, s, sz=24, col=C_WHITE, anchor="la", bold=False):
    d.text(xy, s, font=fnt(sz, bold), fill=col, anchor=anchor)


def section(x, y, num, title, w=None):
    """小节标题：编号 + 标题 + 下划线"""
    d.rounded_rectangle([x, y, x + 46, y + 46], radius=8, fill=C_ACC)
    tex((x + 23, y + 23), num, 26, C_BG1, "mm", True)
    tex((x + 62, y + 23), title, 36, C_WHITE, "lm", True)
    if w:
        d.line([x, y + 62, x + w, y + 62], fill=C_EDGE, width=2)


# ============ 顶部标题区 ============
d.rectangle([0, 0, W, 250], fill=(6, 16, 32))
d.line([0, 250, W, 250], fill=C_ACC, width=4)

tex((W // 2, 78), "「心衡」", 96, C_ACC2, "mm", True)
tex((W // 2, 158), "自感知单导联三参数心电监测前端", 46, C_WHITE, "mm", True)
tex((W // 2, 212), "基于 AMD Zynq-7000 (PYNQ-Z2) 的全硬件定点心电处理链路",
    26, C_DIM, "mm")

# ============ 左栏 ============
LX, LW = 70, 520
y = 300

# 照片
photo = os.path.join(FIG, "photo5_experiment.jpg")
if os.path.exists(photo):
    ph = Image.open(photo).convert("RGB")
    tw = LW
    th = int(ph.height * tw / ph.width)
    ph = ph.resize((tw, th), Image.LANCZOS)
    img.paste(ph, (LX, y))
    d.rounded_rectangle([LX, y, LX + tw, y + th], radius=12, outline=C_ACC, width=3)
    y += th + 14
    tex((LX + tw // 2, y + 14), "真实电极采集 · 现场测量状态", 20, C_DIM, "ma")
    y += 50

# 核心指标卡
card(LX, y, LW, 470)
tex((LX + 24, y + 22), "核心指标", 30, C_ACC2, "la", True)
d.line([LX + 24, y + 66, LX + LW - 24, y + 66], fill=C_EDGE, width=1)

metrics = [
    ("工频抑制比", "−68.5 dB"),
    ("RTL 与模型一致", "2000 / 2000"),
    ("采样时基误差", "0.00 %"),
    ("吞吐量（vs 实时软件）", "70 倍"),
    ("资源占用", "LUT 5.65%"),
    ("时序收敛", "WNS +0.945 ns"),
]
yy = y + 88
for name, val in metrics:
    tex((LX + 26, yy), name, 21, C_DIM, "lm")
    tex((LX + LW - 26, yy), val, 24, C_GOLD, "rm", True)
    yy += 62

# 关键词卡
y += 490
card(LX, y, LW, 300, C_CARD2)
tex((LX + 24, y + 22), "创新关键词", 30, C_ACC2, "la", True)
d.line([LX + 24, y + 66, LX + LW - 24, y + 66], fill=C_EDGE, width=1)
kw = ["自感知信号质量", "单导联三参数", "全硬件定点流水线"]
yy = y + 96
for k in kw:
    d.rounded_rectangle([LX + 24, yy - 22, LX + LW - 24, yy + 26], radius=8,
                        fill=(24, 52, 86), outline=C_ACC, width=1)
    tex((LX + LW // 2, yy + 2), k, 22, C_WHITE, "mm", True)
    yy += 68

# 左栏下方：SQI 对比波形（填满空白 + 最强证据）
y += 330
tex((LX, y), "信号质量评估（硬件输出）", 26, C_ACC2, "la", True)
y += 44
for fn, cap, col in [("wave_clean.png", "无干扰：质量 优秀 3/3", (120, 230, 150)),
                     ("wave_noisy.png", "注入 50 Hz：质量 可疑 1/3", C_GOLD)]:
    fp = os.path.join(FIG, fn)
    if os.path.exists(fp):
        wv = Image.open(fp).convert("RGB")
        tw = LW
        th = int(wv.height * tw / wv.width)
        wv = wv.resize((tw, th), Image.LANCZOS)
        img.paste(wv, (LX, y))
        d.rounded_rectangle([LX, y, LX + tw, y + th], radius=10, outline=col, width=3)
        y += th + 8
        tex((LX + tw // 2, y + 16), cap, 21, col, "ma", True)
        y += 52

# ============ 右栏 ============
RX = 640
RW = W - RX - 70
y = 300

# ① 问题与思路
section(RX, y, "1", "问题与思路", RW)
y += 84
tex((RX, y), "心电信号有两个物理事实：幅度仅 0.3~2 mV，而工频干扰可达数百 mV；", 22, C_WHITE)
tex((RX, y + 34), "QRS 能量集中在 5~15 Hz，50 Hz 工频恰好紧邻其旁。", 22, C_WHITE)
tex((RX, y + 68), "因此一条可用的心电链路必须回答三件事：", 22, C_DIM)
tex((RX + 20, y + 106), "① 定点化后是否还准？  ② 流水线能否收敛？  ③ 采样时基是否成立？", 22, C_ACC2)
y += 160

# ② 系统架构
section(RX, y, "2", "系统架构", RW)
y += 76
arch = os.path.join(FIG, "figA1_arch.png")
if os.path.exists(arch):
    a = Image.open(arch).convert("RGB")
    tw = RW
    th = int(a.height * tw / a.width)
    if th > 470:
        th = 470
        tw = int(a.width * th / a.height)
    a = a.resize((tw, th), Image.LANCZOS)
    ox = RX + (RW - tw) // 2
    img.paste(a, (ox, y))
    d.rounded_rectangle([ox, y, ox + tw, y + th], radius=10, outline=C_EDGE, width=2)
    y += th + 40

# ③ 三项创新
section(RX, y, "3", "三项关键创新", RW)
y += 84

innov = [
    ("自感知信号质量（SQI）",
     "硬件以滤波前后能量比判定数据可信度，四级输出；注入 50 Hz 后由 3/3 降至 1/3。",
     "用三次阈值比较替代除法器：SQI≥80% ⟺ 输出能量×5 ≥ 输入能量×4，零 DSP、零除法。"),
    ("单导联三参数",
     "一条导联同时导出心率、心率变异性与呼吸率，可省去独立的呼吸传感器。",
     "HR 71.97/72；EDR 注入验证 12→11.8 / 15→15.0 / 18→18.2 次·分⁻¹ 全部命中。"),
    ("全硬件定点流水线",
     "陷波、低通、R 波检测、质量评估、HRV 统计全部在 PL 内完成。",
     "Q2.14 定点，与 Python 模型 2000/2000 样本逐位相同，偏移 +0。"),
]
for i, (t1, t2, t3) in enumerate(innov):
    hh = 158
    card(RX, y, RW, hh, C_CARD2)
    d.rounded_rectangle([RX, y, RX + 10, y + hh], radius=4, fill=C_ACC)
    tex((RX + 34, y + 30), t1, 28, C_ACC2, "la", True)
    tex((RX + 34, y + 70), t2, 20, C_WHITE)
    tex((RX + 34, y + 108), t3, 19, C_DIM)
    y += hh + 18

y += 16

# ④ 实测成果
section(RX, y, "4", "实测成果", RW)
y += 76
res = [
    ("无干扰", "质量 3/3 · 能量保留 98.7%"),
    ("注入 50 Hz", "质量 1/3 · 能量保留 39.0%"),
    ("AXI-Stream + DMA", "500 样本连续恢复，峰值 4095（12 位满量程）"),
    ("扫频验证", "72.5~179.9 BPM 五档，R 峰间隔偏差 ≤ 1 采样点"),
]
for name, val in res:
    d.rounded_rectangle([RX, y, RX + 210, y + 46], radius=8, fill=(24, 52, 86))
    tex((RX + 105, y + 23), name, 20, C_ACC2, "mm", True)
    tex((RX + 228, y + 23), val, 21, C_WHITE, "lm")
    y += 54

y += 20

# ⑤ 应用价值
section(RX, y, "5", "应用价值", RW)
y += 76
tex((RX, y), "家庭与社区心血管筛查 · 可穿戴设备前端（省一个呼吸传感器）· 边缘智能的预处理前端", 21, C_WHITE)
tex((RX, y + 36), "由于质量评估与参数提取均在硬件完成，送往主控的只是降维后的特征量而非原始波形。", 21, C_DIM)

# ============ 底部 ============
d.rectangle([0, H - 150, W, H], fill=(6, 16, 32))
d.line([0, H - 150, W, H - 150], fill=C_ACC, width=3)
tex((W // 2, H - 108), "自感知信号质量　·　单导联三参数　·　全硬件定点流水线",
    30, C_ACC2, "mm", True)
tex((W // 2, H - 58), "github.com/eahii250602/ecg-fpga",
    24, C_DIM, "mm")

img.save(OUT_PNG)
img.save(OUT_PDF, "PDF", resolution=150.0)
print("PNG:", OUT_PNG, "%.1f KB" % (os.path.getsize(OUT_PNG) / 1024))
print("PDF:", OUT_PDF, "%.2f MB" % (os.path.getsize(OUT_PDF) / 1024 / 1024))
