# 通用 PYNQ Skill：从「加载 Overlay」到「能稳定读回数据」

> 本 Skill **不依赖任何具体项目模块**。换一块 PYNQ 板、换一个 Overlay，
> 只要按这 8 步走，就能在最短时间内确认「硬件真的在跑，而且跑的是新设计」。

适用：PYNQ 2.7（Zynq-7000 / PYNQ-Z1、Z2）；PYNQ 3.x 见文末差异说明。

---

## 为什么需要这套流程

本项目最初的调试时间有 **两天** 花在「我以为板子上跑的是新比特流」上。
根因有三：
1. `Overlay()` 会**重载比特流并复位全部硬件状态**；
2. 同一个 `.bit` 文件名可能对应多个版本，靠文件名无法判断；
3. 0x00 之类的寄存器常常是**双用途**（频率字 / 数据样本），写错模式时静默丢失。

下面 8 步把这三个坑全部堵上。

---

## Step 1　确认板子在线、版本正确

```bash
hostname -I                      # 应输出板子 IP
cat /proc/device-tree/model      # 应含 "PYNQ"
python3 -c "import pynq; print(pynq.__version__)"
```

**通过判据**：IP 有输出；`pynq.__version__` 为 2.x。

---

## Step 2　校验比特流文件身份（不加载）

```python
import hashlib, pathlib
p = pathlib.Path('/boot/your.bit')
print(p.stat().st_size, hashlib.md5(p.read_bytes()).hexdigest().upper()[:16])
```

**通过判据**：与你 PC 上那份 `.bit` 的 MD5 一致。
**失败怎么办**：SD 卡拷文件时断过电 / 用了旧副本，重新拷。

> 这一步是本 Skill 最有价值的一步。它把「文件是否真的更新了」变成可判定的。

---

## Step 3　加载 Overlay 并等待

```python
import time
from pynq import Overlay
o = Overlay('/boot/your.bit')
time.sleep(1.0)          # ★ 必须等，硬件与 Python 侧的映射需要时间
```

**为什么必须 `sleep`**：本项目实测不加等待时，紧接着的第一次 MMIO 读
有约 30% 概率读到全 0。

**失败怎么办**：报 `RuntimeError: Bitstream download failed` →
先 `cat /boot/BOOT.BIN` 确认启动文件完整；再确认 `.hwh` 与 `.bit` 同名同目录。

---

## Step 4　读版本寄存器，确认「跑的是新设计」

```python
from pynq import MMIO
IP_BASE = 0x43C00000
m = MMIO(IP_BASE, 0x1000)
print(hex(m.read(0x14)))        # 0x14 = VERSION，须由你设计里定义
```

**通过判据**：等于你 RTL 里写死的版本常量（本项目的 `0xEC600008`）。

> **设计要求**：每个自研 IP 都应有一个只读版本寄存器。
> 没有的话，你无法区分「新比特流生效」与「旧比特流仍在跑」。

**失败怎么办**：读回 `0x0` 或 `0xFFFFFFFF` →
地址错 / 该地址未映射 / PL 未配置。

---

## Step 5　确认时钟来源与频率（不要相信文档）

```python
# 方法一：读 AXI 时钟频率寄存器（若设计暴露）
# 方法二：用已知分频器反推 —— 让设计输出一个 1 Hz 方波，用 perf_counter 计时
```

**本项目教训**：Block Design 里配的是 100 MHz，实际 FCLK_CLK0 是 **62.5 MHz**，
因为 `BOOT.BIN` 里的 `ps7_init` 决定时钟，BD 的配置值只是期望值。
这个 2 倍误差直接导致了三个不相关的现象：
采样率偏差、检测阈值失配、心率计算错误。

**通过判据**：用一个已知的时间基准（如 DDS 频率字 + 累加器高位翻转）
测出实际频率，与配置值比对，偏差应 < 0.1%。

---

## Step 6　写一个值、读回来（寄存器连通性）

```python
m.write(0x10, 0x0)          # 先清控制字
m.write(0x00, 0x53)         # 写一个已知值
time.sleep(0.05)
print(hex(m.read(0x00)))    # 若为只读则跳过
```

**目的**：确认写通路与读通路都通。
**注意**：若该地址是只写寄存器（如频率字），读回无意义 —— 要在设计上区分。

---

## Step 7　确认双用途寄存器的当前模式

**这是本项目踩得最深的一个坑。**

很多设计的 `0x00` 是双用途：
- 控制字 `bit3 = 0` → 写入的是**频率字**
- 控制字 `bit3 = 1` → 写入的是**一个数据样本**

如果上一次测试残留 `bit3 = 1`，你先写频率字会被当成样本静默丢弃，
现象是「波形恒为 0、检测数为 0」，但**不报任何错**。

**正确顺序**：
```python
m.write(0x10, 0x0)      # ★ 先清控制字，退出数据模式
time.sleep(0.1)
m.write(0x00, 0x53)     # 再写频率字
time.sleep(0.3)
m.write(0x10, 0x1)      # 最后进入正常工作模式
```

**自检**：写完后等 0.5 秒，读一个「应该增长」的计数器（如检测数、样本数）。
不增长 → 模式没切对。

---

## Step 8　读波形缓冲区（不要用 DMA 做第一次验证）

```python
def grab(m, n, addr0=0):
    out = []
    a = addr0
    for _ in range(n):
        m.write(0x04, a & 0x3FF)     # ★ 注意 bit10 可能是虚拟寄存器选择位
        out.append(m.read(0x0C) & 0xFFFF)
        a += 1
    return out
```

**为什么不先用 DMA**：本项目第一次用 DMA 就因缓冲区少申请一半导致
溢出写坏 DDR，整机冻结、只能断电重启。
**先用 MMIO 逐点读确认数据正确，再上 DMA 测吞吐。**

**失败怎么办**：读回全 0 → 缓冲写指针没动（见 Step 7）；
读回全 65535 → 地址 bit10 误置（进了虚拟寄存器区）。

---

## 排障速查表

| 现象 | 最可能原因 | 先查哪一步 |
|---|---|---|
| `Overlay()` 抛异常 | `.hwh` 与 `.bit` 不同名 / 文件损坏 | Step 2 |
| 版本寄存器读 0 | PL 未配置 / 地址错 | Step 4 |
| 版本寄存器对但数据恒 0 | 双用途寄存器模式错 | Step 7 |
| 数据恒 65535 | 地址 bit10 误置 | Step 8 |
| 第一次读偶尔为 0 | `sleep` 不够 | Step 3 |
| 频率差 2 倍 / 1.6 倍 | 实际时钟与文档不符 | Step 5 |
| DMA 传输后系统冻结 | 缓冲区越界 | Step 8 的注意事项 |

---

## PYNQ 3.x 差异

| 项 | PYNQ 2.7 | PYNQ 3.x |
|---|---|---|
| Overlay 加载 | `Overlay('a.bit')` | `Overlay('a.bit')`（签名兼容，但 hwh 改为 `pynq.overlay.Overlay`） |
| MMIO | `MMIO(base, size)` 相同 | 相同 |
| DMA | `pynq.lib.dma.DMA` | `pynq.lib.dma.DMA` |
| 设备树模型 | `PYNQ` | `PYNQ-Z2` 等具体型号 |

---

## 本 Skill 的来源

全部 8 步都来自本项目的**真实故障**，不是教科书推导：

| Step | 对应的真实故障 |
|---|---|
| 2 | 换了 RTL 但板上没变，误判为「改动无效」 |
| 3 | `Overlay()` 后立即读，30% 概率读到 0 |
| 4 | 无法区分新旧比特流，白改三轮 |
| 5 | 时钟 62.5 vs 100 MHz，导致三个不相关现象 |
| 7 | 0x00 双用途寄存器，波形恒 0 且不报错 |
| 8 | DMA 缓冲区越界，整机冻结需断电 |
