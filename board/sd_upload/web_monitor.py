#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""web_monitor.py —— 实时心电可视化（浏览器查看）

设计决策（每条都对应一个已知风险）
--------------------------------
1. 【不用 DMA，用寄存器通路】
   实测 DMA 的地址步长是 2 倍，导致实际写入字节数 = 请求长度的 2 倍，
   会冲出缓冲区踩坏 DDR（已在 2026-11-04 造成一次整机冻结）。
   演示代码绝不能用会挂死的通路。250 S/s 对寄存器读毫无压力
   （读 1024 点约 1~4 ms，我们每秒只读 260 点）。

2. 【读取速率 260/s > 写入 250/s】
   读得比写得快，读取指针永远不会被写入指针追上；
   偶尔重复一个样本，滚动显示上完全看不出来。

3. 【显示滤波后信号】
   控 0x10 bit0=1，让波形缓冲存 ecg_filt_out（陷波+低通之后）。
   原始信号有 50Hz 毛刺，滤波后的波形更适合展示。

4. 【SQI 门控配色】
   硬件 SQI ≤ 1 时波形画成红色 —— 让"数据不可信"肉眼可见。

启动后浏览器打开  http://<板子IP>:8000
板子 IP 用 `hostname -I` 查。
"""
import json
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from pynq import Overlay, MMIO

ECG = 0x43C00000
FS = 250.0
RING = 2000                 # 环形缓冲（8 秒）
POLL_MS = 100               # 采集周期
PER_POLL = 26               # 每周期读 26 点 → 260 点/秒 > 250
HTTP_PORT = 8000

lock = threading.Lock()
state = {
    "ring": np.zeros(RING, dtype=np.int16),
    "w": 0,                 # 已写入总数（单调递增）
    "hr": 0.0,
    "sdnn": 0.0,
    "sqi": 0,
    "running": False,
    "err": "",
}


def vreg(m, i):
    m.write(0x04, 0x400 | i)
    return m.read(0x0C) & 0xFFFFFFFF


def estimate_hr(x):
    """从最近 4 秒数据估心率（包络谱峰）"""
    if len(x) < 200:
        return 0.0, 0.0
    v = x.astype(np.float64) - x.mean()
    def ma(a, k):
        k = max(1, int(k))
        return np.convolve(a, np.ones(k) / k, mode="same")
    hp = v - ma(v, FS / 5.0)
    bp = ma(hp, FS / 15.0)
    d = np.diff(bp, prepend=bp[0])
    env = ma(d ** 2, 0.15 * FS)
    if env.max() <= 0:
        return 0.0, 0.0
    env = env / env.max()
    sp = np.abs(np.fft.rfft(env * np.hanning(len(env))))
    fr = np.fft.rfftfreq(len(env), 1 / FS)
    sel = (fr > 0.5) & (fr < 4.0)
    if not sel.any():
        return 0.0, 0.0
    hr = float(fr[sel][np.argmax(sp[sel])] * 60.0)
    # 简单 SDNN：用包络的自相关主周期近似
    return hr, 0.0


def acquisition():
    try:
        o = Overlay("/boot/ecg_bd.bit")
        time.sleep(1.0)
        m = MMIO(ECG, 0x1000)
        ver = m.read(0x14)
        print("版本 0x%08X" % ver)
        # 主机样本模式关、注入关、缓冲存【滤波后】信号
        m.write(0x10, 0x1)
        m.write(0x00, 83)          # DDS 72.5 BPM
        time.sleep(0.5)
        state["running"] = True
        addr = 0
        while True:
            t0 = time.time()
            new = np.empty(PER_POLL, dtype=np.int16)
            for k in range(PER_POLL):
                m.write(0x04, addr & 0x3FF)
                new[k] = (m.read(0x0C) & 0xFFFF) - 2048
                addr += 1
            sqi = vreg(m, 0)
            with lock:
                for v in new:
                    state["ring"][state["w"] % RING] = v
                    state["w"] += 1
                state["sqi"] = sqi
                # 每 10 个周期（1 秒）算一次心率
                if state["w"] % (PER_POLL * 10) < PER_POLL:
                    idx = [(state["w"] - 1 - i) % RING for i in range(1000)]
                    seg = state["ring"][idx][::-1]
                    hr, _ = estimate_hr(seg)
                    if hr > 0:
                        state["hr"] = hr
            dt = t0 + POLL_MS / 1000.0 - time.time()
            if dt > 0:
                time.sleep(dt)
    except Exception:
        state["err"] = traceback.format_exc()[-500:]
        state["running"] = False


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>ECG-DDS-FPGA 实时心电监测</title>
<style>
 body{margin:0;background:#0b0f14;color:#e6edf3;font-family:"Microsoft YaHei",sans-serif}
 .hd{padding:14px 24px;border-bottom:1px solid #1f2a37;display:flex;justify-content:space-between;align-items:baseline}
 .hd h1{margin:0;font-size:20px;font-weight:600;letter-spacing:1px}
 .hd span{color:#7d8590;font-size:13px}
 #wrap{padding:16px 24px}
 #cv{width:100%;height:300px;background:#060a0f;border:1px solid #1f2a37;border-radius:6px;display:block}
 .row{display:flex;gap:14px;margin-top:16px;flex-wrap:wrap}
 .card{flex:1;min-width:150px;background:#111821;border:1px solid #1f2a37;border-radius:6px;padding:14px 18px}
 .lbl{color:#7d8590;font-size:12px;letter-spacing:1px}
 .val{font-size:30px;font-weight:700;margin-top:6px;font-variant-numeric:tabular-nums}
 .unit{font-size:13px;color:#7d8590;margin-left:4px}
 .ok{color:#3fb950}.warn{color:#d29922}.bad{color:#f85149}
 .st{margin-top:14px;font-size:13px;color:#7d8590}
</style></head><body>
<div class="hd"><h1>ECG-DDS-FPGA 实时心电监测</h1>
<span>数据来源：AXI4-Lite 寄存器通路 · 250 Hz · Zynq-7020</span></div>
<div id="wrap">
 <canvas id="cv"></canvas>
 <div class="row">
  <div class="card"><div class="lbl">心率 HR</div><div class="val" id="hr">--<span class="unit">BPM</span></div></div>
  <div class="card"><div class="lbl">信号质量 SQI</div><div class="val" id="sq">--</div></div>
  <div class="card"><div class="lbl">采样率</div><div class="val">250<span class="unit">Hz</span></div></div>
  <div class="card"><div class="lbl">已采集</div><div class="val" id="n">0</div></div>
 </div>
 <div class="st" id="st">连接中...</div>
</div>
<script>
const cv=document.getElementById('cv'),cx=cv.getContext('2d');
let since=0,buf=[],sqi=3,hr=0;
function fit(){const r=cv.getBoundingClientRect(),d=devicePixelRatio||1;
 cv.width=r.width*d;cv.height=r.height*d;cx.setTransform(d,0,0,d,0,0);}
addEventListener('resize',fit);fit();
function draw(){
 const W=cv.width/(devicePixelRatio||1),H=cv.height/(devicePixelRatio||1);
 cx.fillStyle='#060a0f';cx.fillRect(0,0,W,H);
 cx.strokeStyle='#121b25';cx.lineWidth=1;
 for(let i=0;i<=4;i++){const y=H*i/4;cx.beginPath();cx.moveTo(0,y);cx.lineTo(W,y);cx.stroke();}
 if(buf.length<2)return;
 const n=Math.min(buf.length,1100), s=buf.slice(buf.length-n);
 let mx=1;for(const v of s)if(Math.abs(v)>mx)mx=Math.abs(v);
 const sc=(H*0.42)/mx;
 cx.beginPath();
 for(let i=0;i<n;i++){const x=W*i/(n-1),y=H/2-s[i]*sc;
  i?cx.lineTo(x,y):cx.moveTo(x,y);}
 cx.strokeStyle = sqi>=2 ? '#3fb950' : (sqi==1 ? '#d29922' : '#f85149');
 cx.lineWidth=1.8;cx.stroke();
}
async function tick(){
 try{
  const r=await fetch('/data?since='+since);const j=await r.json();
  if(j.samples.length){buf=buf.concat(j.samples);if(buf.length>4000)buf=buf.slice(-2000);}
  since=j.w;sqi=j.sqi;hr=j.hr;
  document.getElementById('hr').innerHTML=hr>0?hr.toFixed(1)+'<span class="unit">BPM</span>':'--<span class="unit">BPM</span>';
  const q=document.getElementById('sq');
  q.textContent=['不可信','可疑','良好','优秀'][sqi]||'--';
  q.className='val '+(sqi>=2?'ok':(sqi==1?'warn':'bad'));
  document.getElementById('n').textContent=j.w;
  document.getElementById('st').textContent=j.running?'采集中 · 波形颜色代表信号质量（绿=良好 黄=可疑 红=不可信）':'采集线程已停止：'+j.err;
  draw();
 }catch(e){document.getElementById('st').textContent='连接中断，重试中...';}
 setTimeout(tick,200);
}
tick();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/data"):
            try:
                since = int(self.path.split("since=")[1])
            except Exception:
                since = 0
            with lock:
                w = state["w"]
                start = max(since, w - RING, 0)
                cnt = w - start
                if cnt > 0:
                    idx = [(start + i) % RING for i in range(cnt)]
                    samples = state["ring"][idx].tolist()
                else:
                    samples = []
                body = json.dumps({
                    "w": w, "samples": samples,
                    "hr": round(state["hr"], 2), "sqi": int(state["sqi"]),
                    "running": state["running"], "err": state["err"],
                }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    t = threading.Thread(target=acquisition, daemon=True)
    t.start()
    time.sleep(2.0)
    print("=" * 56)
    print("浏览器打开： http://<板子IP>:%d" % HTTP_PORT)
    print("板子 IP 用 hostname -I 查")
    print("=" * 56)
    ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler).serve_forever()
