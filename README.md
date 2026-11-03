# ECG-DDS-FPGA — 基于 PYNQ-Z2 的实时心电信号处理链路

> 在 Xilinx Zynq-7020 上实现「心电波形生成 → 50 Hz 工频抑制 → Pan-Tompkins R 波检测 → 心率/HRV 输出」的全硬件流水线，
> 并用 PYNQ Overlay 暴露给 Python，支持真实模拟前端（AD8232 + XADC）接入。

[![Platform](https://img.shields.io/badge/Platform-PYNQ--Z2%20(xc7z020)-blue)]()
[![Tool](https://img.shields.io/badge/Vivado-2026.1-orange)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

---

## 一、核心结果（全部为板级实测，非仿真值）

| 指标 | 数值 | 证据 |
|---|---|---|
| **50 Hz 抑制比** | **−68.5 dB** | `board/host_ecg.py` A3；受 12 位量化下限限制，理论 −94.8 dB |
| **RTL 与定点模型一致性** | **2000/2000 逐位相同**（偏移 +0） | `sim/filt/compare_rtl.py` |
| **时序收敛** | **WNS +0.741 ns / TNS 0 / 失败端点 0**（共 7824） | `impl_1` 时序报告 |
| **资源占用** | LUT 1788 (3.36%)、FF 2522 (2.37%)、BRAM 1.5、**DSP 17** | 同上 |
| **Pan-Tompkins 心率跟随** | **72.5 / 90.8 / 108.3 / 145.0 / 179.9 BPM 全档**，误差 ±1 采样点 | `board/pt_check.py` 扫频 |
| **采样时基准确度** | 均值误差 **+0.00%**（250.00 Hz），抖动 **3.9 µs** | `board/rate_check.py` |
| **波形缓冲** | 1024 点 @ 250 Hz 环形缓冲，AXI 可回读 | `ecg_axi.v` |

---

## 二、系统架构

```
                    ┌──────────────────────────── Zynq-7020 (PL) ─────────────────────────────┐
                    │                                                                        │
  真实模拟前端        │   ┌──────────┐   ┌──────────┐   ┌──────────────────┐   ┌──────────┐   │
  AD8232 ──分压──▶ XADC ──▶│ 主机样本 │──▶│ noise50  │──▶│    ecg_filt      │──▶│ pt_chain │──▶ RR
  (J5 VP/VN)        │      │  选择器  │   │ 注入器   │   │ 陷波50 + 低通40  │   │ Pan-     │   HRV
                    │      └──────────┘   │ (测试用) │   │ Q2.14 · DF-I     │   │ Tompkins │   │
  内部 DDS 波形      │           ▲        └──────────┘   └──────────────────┘   └──────────┘   │
  ecg_rom(256×12) ──┼───────────┘                              │                              │
                    │                                          ▼                              │
                    │                              ┌──────────────────────┐                   │
                    │                              │ 波形缓冲 1024×32 (BRAM)│                  │
                    │                              └──────────────────────┘                   │
                    └──────────────────────────────┬─────────────────────────────────────────┘
                                                   │ AXI4-Lite
                                        ┌──────────▼──────────┐
                                        │  PYNQ / Python (PS) │
                                        │  寄存器读写 · 分析   │
                                        └─────────────────────┘
```

### 寄存器映射（基址 `0x43C00000`）

| 偏移 | 访问 | 名称 | 说明 |
|---|---|---|---|
| `0x00` | W | `FTW` | DDS 频率字；**主机样本模式下改为样本值**（低 12 位有符号） |
| `0x04` | W | `WAVE_ADDR` | 波形缓冲读地址（0~1023） |
| `0x08` | R | `RR_COUNT` | 旧版检测器 RR 间隔（采样点数） |
| `0x0C` | R | `WAVE_DATA` | 波形数据（32 位符号扩展） |
| `0x10` | R/W | `FILT_CTL` | `[23:8]` 注入幅度 · `bit2` 注入使能 · `bit1` PT 源 · `bit0` 缓冲源 · `bit3` 主机样本模式 |
| `0x14` | R | `VERSION` | **`0xEC600005`** |
| `0x18` | R | `PT_RR` | Pan-Tompkins RR 间隔 |
| `0x1C` | R | `PT_DET_CNT` | PT 累计检测次数 |

---

## 三、仓库结构

```
ecg/
├── ip_repo/ecg_axi_1_0/        # 自研 AXI IP（RTL 源码 + IP 打包描述）
│   ├── hdl/                    #   ecg_axi.v / ecg_filt.v / noise50.v / dds_ecg.v / pt_chain_serial.v ...
│   └── component.xml
├── vivado/                     # 工程脚本（构建产物不入库）
│   ├── rebuild_phase1.tcl      #   清理 .gen 缓存（防 Vivado 用旧 HDL）
│   ├── rebuild_phase2.tcl      #   综合 + 实现 + 出比特流
│   └── set_clk62.tcl
├── sim/                        # 仿真与模型
│   ├── filt/                   #   定点模型（Python）+ RTL testbench + 逐位对账
│   └── pt_dp625/
├── python/                     # PC 侧分析脚本（定点滤波器、心电分析）
├── board/                      # 板端脚本（拷到 SD 卡 /boot 下运行）
│   ├── sd_upload/
│   └── backup/                 #   已知可用比特流归档
├── report/                     # 开发日志与阶段总结
│   ├── WORKLOG.md              #   ★ 全量开发日志（含每次判断依据与纠错轨迹）
│   └── progress.md
├── skill/                      # ★ 通用 PYNQ 技能包（与题目解耦，换板可用）
├── docs/                       # 文档
│   └── llm-collab.md           #   ★ 大模型协作记录（提示词/回答/自我纠错）
└── README.md
```

---

## 四、快速开始

### 硬件

| 件 | 型号/参数 |
|---|---|
| 开发板 | PYNQ-Z2（Zynq-7020, `xc7z020clg400-1`） |
| 模拟前端（可选） | AD8232 心电模块 + 3 片 Ag/AgCl 电极 |
| 分压 | 2.7 kΩ + 0.93 kΩ（÷3.90，把 0~3.3 V 压到 XADC 的 0~1.0 V） |
| 连接 | AD8232 OUT → 分压 → **J5 的 VP 孔**；J5 的 VN、GND → GND |

> **J5 位置**：板子下边缘、`SD CARD ON BACK` 丝印框左侧，4 个孔，丝印自上而下为 **`GND` / `VN` / `VP`**。
> ⚠️ 必须按丝印接，不能按脚号接。

### 软件

```bash
# 1. 把 board/sd_upload/ 下的文件拷到 SD 卡的 FAT 分区（板上即 /boot）
#    包括 ecg_bd.bit、ecg_bd.hwh 及各 .py

# 2. 板子上电，串口登录（115200 8N1）
sudo -s
python3 /boot/host_ecg.py       # 主机通道 + 硬件陷波自测（判据 -20 dB）
python3 /boot/rate_check.py     # 采样时基对比（sleep vs 忙等）
python3 /boot/filt_check.py     # 滤波链两阶段验收
python3 /boot/pt_check.py       # Pan-Tompkins 心率跟随
```

### 从零构建（约 10 分钟）

```bash
vivado -mode batch -source vivado/rebuild_phase1.tcl   # 清 .gen 缓存
vivado -mode batch -source vivado/rebuild_phase2.tcl   # 综合+实现+比特流
```

> **必做校验**：phase1 之后确认 `ecg_system.gen/sources_1/bd/ecg_bd/ipshared/*/hdl/` 里
> 已包含最新 HDL（比对版本号或新增信号名）。Vivado 的 IP 缓存不失效会导致"源码改了、
> 综合却用旧代码"，见 `skill/vivado-rebuild-guard/`。

---

## 五、关键设计决策与依据

| # | 决策 | 依据（实测数字） |
|---|---|---|
| 1 | **滤波器用 IIR 不用 FIR** | 0.5 Hz 高通在 250 Hz 采样下，FIR 需约 2000 抽头；IIR 每级仅 5 次乘法 |
| 2 | **系数格式 Q2.14 而非 Q1.15** | Q1.15 装不下 0.5 Hz 高通的 `b1=-1.9823`，会**静默截断**成 −1.0，滤波器彻底失效且不报错 |
| 3 | **每级拆 3 拍流水** | v1 把"5 乘法+5 累加+移位+饱和"塞一拍 → **WNS −6.363 ns / 289 端点违例**；拆 3 拍后 **+0.741 ns** |
| 4 | **饱和比较先右移再比** | 右移 14 位后只剩 22 位有效，比较位宽从 36 位降到 22 位，省 14 级进位链 |
| 5 | **滤波输入加二选一（主机样本模式）** | 让真实 ADC 样本能进 RTL 链；默认 bit3=0，行为与旧版完全一致，无回归 |
| 6 | **采样用 perf_counter 忙等** | `sleep(0.004)` 实测 **4.228 ms（+5.70%）** → 50 Hz 被看成 52.85 Hz，**偏离陷波中心 2.85 Hz（带宽 ±1.9 Hz）→ 陷波器失效**；忙等后 **250.00 Hz** |
| 7 | **PL 内建 50 Hz 注入器** | 板上无外部信号源时，滤波器"无物可滤"；把激励做进 FPGA，可复现、可随比特流交付 |
| 8 | **抑制比用 FTW=0 单独测** | 心电 R 波峰值 2047 已达 12 位上限，叠加 600 LSB 注入会**饱和削顶**，且 R 波频谱泄漏到 50 Hz → 把 −53 dB 误测成 −3.4 dB |

---

## 六、已知限制（如实记录）

| 限制 | 现状 | 原因 |
|---|---|---|
| **真实心电波形** | 未采到 | AD8232 输出幅度约 0.23 mV，低于当前噪声；前端增益不足 |
| **采样由软件驱动** | 250 Hz 闭环忙等 | 未实现硬件定时采集（DMA/AXI-Stream） |
| **技术栈覆盖** | 全程 AXI-Lite 寄存器轮询 | 未使用 AXI-Stream / DMA / HLS |
| **时基抖动** | 3.9 ~ 57 µs | Linux 调度抢占，非代码问题 |
| **XADC 自检脚本** | `xadc_selftest.py` 的版本期望值未同步 | 不影响 XADC 读数，仅影响那一行判定 |

---

## 七、技能包

见 [`skill/`](skill/) 目录。每个 Skill 都刻意**与本项目解耦**，换题目、换板卡仍可用：

| Skill | 解决什么问题 |
|---|---|
| [`pynq-overlay-guard`](skill/pynq-overlay-guard/) | Overlay 加载的四类经典故障：版本不符、路径选错、复位未释放、XRT 环境未 source |
| [`rtl-golden-compare`](skill/rtl-golden-compare/) | RTL 与 Python 定点模型逐位比对 + 偏移扫描，自动区分"等价 / 错位 / 失败" |
| [`vivado-rebuild-guard`](skill/vivado-rebuild-guard/) | 分阶段重建 + 强制验证 IP 缓存已更新 + 自动提取 WNS/资源/MD5 |

---

## 八、许可

MIT License — 见 [LICENSE](LICENSE)。
