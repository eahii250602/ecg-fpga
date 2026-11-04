# -*- coding: utf-8 -*-
"""把 docs/技术文档.md 转成带图的 Word 文档"""
import os
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

MD = r"D:\ecg\docs\技术文档.md"
FIG = r"D:\ecg\report\figs"
OUT = r"D:\ecg\docs\心衡_技术文档.docx"

# 各章节末尾插入的图
INSERTS = {
    "2.1 整体介绍": [("figA1_arch.png", "图 A1  系统六层架构"),
                     ("figA2_rtl.png", "图 A2  PL 内部数据流")],
    "2.2.3 电路各模块介绍": [("figA3_divider.png", "图 A3  XADC 输入分压网络")],
    "2.3.1 软件整体介绍": [("figA4_sw.png", "图 A4  PS 侧软件模块组成")],
    "2.3.2 软件各模块介绍": [("figA5_flow.png", "图 A5  采集与推送流程")],
    "3.1 整体介绍": [("photo5_experiment.jpg", "图 B1  系统整体（现场测量状态）"),
                     ("photo1_board_top.jpg", "图 B2  系统俯视图（开发板 + 面包板 + 上位机）")],
    "3.2.2 电路成果": [("photo4_breadboard.jpg", "图 B3  分压网络与跳线（面包板特写）"),
                       ("photo3_ad8232.jpg", "图 B4  AD8232 单导联前端模块"),
                       ("photo2_board_angle.jpg", "图 B5  系统斜视图")],
}


def set_font(run, name="宋体", size=10.5, bold=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def add_para(doc, text, style=None, size=10.5, bold=False, color=None,
             align=None, indent=True):
    p = doc.add_paragraph(style=style)
    if align:
        p.alignment = align
    if indent and style is None:
        p.paragraph_format.first_line_indent = Pt(21)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.4
    # 处理 **粗体** 片段
    for seg in re.split(r"(\*\*[^*]+\*\*)", text):
        if not seg:
            continue
        if seg.startswith("**") and seg.endswith("**"):
            r = p.add_run(seg[2:-2])
            set_font(r, size=size, bold=True, color=color)
        else:
            r = p.add_run(seg)
            set_font(r, size=size, bold=bold, color=color)
    return p


def add_image(doc, fname, caption):
    path = os.path.join(FIG, fname)
    if not os.path.exists(path):
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    from PIL import Image as _I
    try:
        _w, _h = _I.open(path).size
    except Exception:
        _w, _h = 4, 3
    _cm = 9.0 if _h > _w else 14.0
    p.add_run().add_picture(path, width=Cm(_cm))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run(caption)
    set_font(r, size=9, color=RGBColor(0x59, 0x59, 0x59))
    c.paragraph_format.space_after = Pt(10)


def flush_table(doc, rows):
    if not rows:
        return
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [c for c in cells if not all(re.fullmatch(r":?-{2,}:?", x or "-") for x in c)]
    if not cells:
        return
    ncol = max(len(r) for r in cells)
    t = doc.add_table(rows=len(cells), cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(cells):
        for j in range(ncol):
            cell = t.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            r = p.add_run(row[j] if j < len(row) else "")
            set_font(r, size=9, bold=(i == 0))
            p.paragraph_format.space_after = Pt(0)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)


doc = Document()
st = doc.styles["Normal"]
st.font.name = "宋体"
st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

lines = open(MD, encoding="utf-8").read().splitlines()
i = 0
tbl = []
cur_sec = ""

while i < len(lines):
    ln = lines[i].rstrip()

    # 表格收集
    if ln.startswith("|"):
        tbl.append(ln)
        i += 1
        continue
    if tbl:
        flush_table(doc, tbl)
        tbl = []

    if not ln.strip() or ln.strip() == "---":
        i += 1
        continue

    # 标题
    if ln.startswith("### "):
        cur_sec = ln[4:].strip()
        h = doc.add_heading(level=3)
        r = h.add_run(cur_sec)
        set_font(r, "黑体", 12, True)
    elif ln.startswith("## "):
        txt = ln[3:].strip()
        cur_sec = txt
        h = doc.add_heading(level=2)
        r = h.add_run(txt)
        set_font(r, "黑体", 14, True)
    elif ln.startswith("# "):
        h = doc.add_heading(level=1)
        r = h.add_run(ln[2:].strip())
        set_font(r, "黑体", 16, True)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif ln.startswith(">"):
        add_para(doc, ln.lstrip("> ").strip(), size=9.5,
                 color=RGBColor(0x59, 0x59, 0x59), indent=False)
    else:
        add_para(doc, ln)

    # 章节末尾插图
    nxt = ""
    for k in range(i + 1, min(i + 4, len(lines))):
        if lines[k].startswith("#"):
            nxt = lines[k]
            break
    if nxt.startswith("#") and cur_sec in INSERTS:
        for f, cap in INSERTS.pop(cur_sec):
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            add_image(doc, f, cap)
    i += 1

if tbl:
    flush_table(doc, tbl)

doc.save(OUT)
print("已生成:", OUT)
print("大小: %.1f KB" % (os.path.getsize(OUT) / 1024))
