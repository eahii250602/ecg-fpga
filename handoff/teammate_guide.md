# 学习指南（赶进度 · 基础项目版）

> **目标**：掌握项目需要的技能，并看懂现有潦草版项目（软件部分已完结），组内追平进度，尽量快，不需要完整复现我已经做的，但要看懂学会；
> **总计划**（三个人都要做的）：潦草版项目全面升级 - 扩展（多）功能，升级（深）功能，联系现实（应用）

---
 
整体学习建议：理论（了解本质，了解框架，和ai多轮聊天）+ 实验（ai生成代码阅读 + 操作vivado + 复现功能）

# 第一部分：技能学习任务
（具体内容自己问ai要学什么，下面的不完整不准确）

## 1. 数电基础

- 组合逻辑 vs 时序逻辑
- 触发器（D 触发器）、寄存器、计数器、移位寄存器
- 时钟、上升沿、复位（同步复位/异步复位）
- 二进制、补码、有符号数、位宽与溢出
- 进位链、查找表（LUT）、Block RAM、DSP 等FPGA 资源

## 2. Verilog 基础

- `module` / `input` / `output` / `wire` / `reg` 的含义与区别
- `always @(posedge clk)` 时序块、`assign` 连续赋值
- 非阻塞赋值 `<=` vs 阻塞赋值 `=`
- 参数 `parameter`、`localparam`、位拼接 `{}`、位选择 `[n:m]`
- 模块例化（怎么把一个模块接进另一个模块）
- **测试台（testbench）怎么写**：`initial`、`#` 延时、`$finish`、`$dumpvars`


## 3. Vivado 环境（下载 + 熟悉）

- 会创建工程、添加源文件、添加仿真文件
- 会跑**仿真**（Run Simulation → Behavioral），会看波形（waveform 窗口，加信号、看值）
- 会跑**综合**（Synthesis）和**实现**（Implementation），会看资源报告
- 知道 `.xdc` 约束文件是干嘛的（本阶段只需了解）

## 4. 上板实验（我也还没搞定）

- 什么是比特流 `.bit`，怎么下载到 FPGA
- JTAG 是什么
- PYNQ-Z2 板子的接口（micro-USB、网口、SD 卡、PMOD、LED/按键）
- 串口终端（115200 波特率）怎么看板子输出


## 5. Zynq 芯片 & PYNQ 框架（了解）

- Zynq = **PS（ARM 处理器）+ PL（FPGA 逻辑）** 两部分，中间通过 **AXI 总线**通信
- **PYNQ 框架**的本质：板子上的 Linux 里跑 Python，Python 通过加载 overlay（`.bit`+`.hwh`）控制 PL

、
---

# 第二部分：基础项目整体脉络（4 大模块）
潦草版项目务必先看懂，以下只是简介，请多问ai，深入看懂

## 模块 1：DDS 心电波形发生器

**理论**：DDS（Direct Digital Synthesis，直接数字频率合成）的核心是"用数字累积相位，再查表出波形"。一个 32 位相位累加器，每个时钟周期加一个固定增量 FTW（Frequency Tuning Word，频率控制字），输出频率 `f_out = FTW × f_clk / 2^32`。我们取相位累加器的**高 8 位**去寻址一个 256 点的查找表，表里存的是用 Python 离线算好的心电波形（P-QRS-T），而不是正弦波。于是"改一个数字 FTW"就能精确控制心率。

**本质**：一条"数字 → 相位 → 地址 → 波形"的流水。两个关键概念：**相位累积**（32 位保证 0.023Hz 的分辨率）和**相位截断**（高 8 位让表只需 256 点，省资源，代价是极小的相位误差）。波形用**偏移二进制**存（2048=基线），读出时减 2048 转成有符号数。

**实验**（`tb_dds_ecg.v`）：仿真时钟设 **1.25MHz**（比 100MHz 慢 80 倍，波形完全等价但跑得快、省内存），FTW 由公式自动推导。先跑 60 BPM（1 秒一搏），再改 FTW 跑 180 BPM（0.34 秒一搏）。观察：波形是"心电"不是正弦；改 FTW 后心跳明显变快。

**代码**：`dds_ecg.v`（相位累加 + 截断）、`ecg_rom.v`（256×12 查找表，数据内嵌）。

---

## 模块 2：R 波检测及计数

**理论**：心电有 P、QRS、T 三个特征波，R 波是最高最尖的正峰（我们波形里 R=2047、T=614）。测心率 = 测 R 波之间的间隔（RR 间期）。三步：① `tick_gen` 分频出 **250Hz 采样节拍**（每 4ms 采一点，是真实监护仪惯例）；② **阈值比较**（阈值 1200，正好卡在 T 波 614 和 R 波 2047 之间）；③ 加 **200ms 不响应期（blanking）**，防止 R 波后面紧跟的 T 波被误判成第二个 R 波（否则心率直接翻倍）。

**本质**：一个**两状态状态机**——`IDLE`（等超阈值）和 `BLANK`（不响应期）。`r_detect` 输出是"与采样节拍对齐的单周期脉冲"。`rr_counter` 数两次 R 波之间过了多少采样点（72 次/分 ≈ 208 点）。

**实验**：`tb_r_detect.v` 单独验证 blanking——连续给"R 波 → 10 tick 后的 T 波 → 40 tick 后的真 R 波"，看 `r_detect` 只在正确的两个位置输出、T 波被屏蔽。`tb_ecg_detect.v` 做端到端：72BPM → rr_count≈208，180BPM → rr_count≈83。

**代码**：`tick_gen.v`（分频）、`r_detect.v`（状态机）、`rr_counter.v`（计数）。

---

## 模块 3：AXI 联通

**理论**：PS（ARM）要控制 PL（FPGA），需要一条标准总线。**AXI4-Lite** 是 ARM/Xilinx 定义的轻量总线协议，用 5 个通道完成读写：写地址 AW、写数据 W、写响应 B、读地址 AR、读数据 R。握手规则：**VALID 和 READY 在同一时钟沿同时为高，才算一次传输**。我们的 IP 把 6 个寄存器映射到一段地址（0x00~0x14），Python 读写这些地址 = 读写寄存器。

**本质**：AXI 从机核心是"地址译码 + 读写通道状态机"。Vivado 给了模板，我们改的是**寄存器映射**和**信号怎么进出**——用"寄存器穿透"（在从机开 output/input 端口，把 FTW 送出去给 DDS、把 rr_count 接回来给 Python 读）。这体现了软硬件接口设计的基本手法。

**实验**：上板后 Python 写 `0x00`=FTW、读 `0x14`=版本号 `0xEC600001`（自检通路）、读 `0x08`=rr_count。这是"全链集成"前的关键验证。

**代码**：`ecg_axi_slave_lite_v1_0_S00_AXI.v`（从机）、`ecg_axi.v`（顶层，例化从机 + 整条信号链）。

---

## 模块 4：全链集成仿真

**理论**：把 DDS、tick_gen、阈值比较、r_detect、rr_counter **串成一条流水线**：写 FTW → DDS 生成波形 → 250Hz 采样 → 阈值比较 → R 检测 → RR 计数 → 读 rr_count。这验证的是"整条检测链从输入到输出是否工作"。

**本质**：理解**信号流**——每个模块只做一件小事，用 wire 连起来，数据像水一样流过。这是数字系统设计的根本方法：**分而治之 + 层次化例化**。看懂这个，就看懂了 FPGA 项目的基本骨架。

**实验**：`tb_ecg_detect.v` 是端到端测试台，用 `SIM_MODE` 开关切换仿真时钟（1.25MHz）和上板时钟（100MHz），FTW 也随之切换。跑完看 rr_count 是否 ≈208（72BPM）/≈83（180BPM）。

**代码**：`tb_ecg_detect.v`（把 5 个模块例化连起来 + 时钟/复位/激励）。

---

# 第三部分：代码阅读指南
（这是基础项目四步骤的所有代码，务必全部读完并看懂，但不要求会写）

## 3.1 先读"小模块“

| 顺序 | 文件 | 看什么 | 行数 |
|---|---|---|---|
| 1 | `ecg_rom.v` | 查找表：`mem[0:255]` 数组 + `initial` 填数据 + 同步读 | 96 |
| 2 | `tick_gen.v` | 计数器分频：`$clog2` 自动算位宽、单周期脉冲 | 32 |
| 3 | `rr_counter.v` | 计数：`rr_count` 锁存 + `rr_valid` 标志 | 39 |
| 4 | `r_detect.v` | **状态机**：`S_IDLE`/`S_BLANK`、转移条件、Mealy 输出 | 46 |
| 5 | `dds_ecg.v` | 相位累加器 + 截断 + 例化 ROM | 41 |

## 3.2 再读"顶层集成"

| 顺序 | 文件 | 看什么 |
|---|---|---|
| 6 | `ecg_axi.v` | 顶层：例化从机 + 例化 5 个模块 + 用 wire 连起来（**重点看"信号怎么流"**） |
| 7 | `ecg_axi_slave_lite_v1_0_S00_AXI.v` | AXI 从机：**地址译码（写）**、**读选择器**、`reg_*` 穿透信号 |

## 3.3 最后读测试台

| 顺序 | 文件 | 看什么 |
|---|---|---|
| 8 | `tb_dds_ecg.v` | 时钟生成、复位、改 FTW、`$dumpvars` |
| 9 | `tb_r_detect.v` | `task` 造采样节拍、造 R/T 波场景 |
| 10 | `tb_ecg_detect.v` | 端到端：例化 5 个模块 + `SIM_MODE` 开关 |

---

# 第四部分：工程打开指南

## 4.1 交接包结构（你收到的就是这个）

```
   handoff\
   ├── teammate_guide.md      ← 本指南
   ├── rtl\                   ← 7 个设计文件
   │      dds_ecg.v / ecg_rom.v / tick_gen.v / r_detect.v /
   │      rr_counter.v / ecg_axi.v / ecg_axi_slave_lite_v1_0_S00_AXI.v
   ├── tb\                    ← 3 个测试台
   │      tb_dds_ecg.v / tb_r_detect.v / tb_ecg_detect.v
   └── data\
          ecg_256x12.mem      ← 波形原始数据（现已内嵌进 ecg_rom.v，仅供理解）
```

## 4.2 怎么在 Vivado 里看

**★ 推荐方式（自己建工程，顺便练手）**：
1. Create Project → 名字随意 → RTL Project → Next
2. 器件选 `xc7z020clg400-1`（PYNQ-Z2 的芯片）→ Next → Finish
3. Add Sources：把 `rtl\` 下的 5 个**模块**加进去
   （`dds_ecg.v / ecg_rom.v / tick_gen.v / r_detect.v / rr_counter.v`）
   ⚠️ 先**不要**加 `ecg_axi.v` 和 `ecg_axi_slave_lite_v1_0_S00_AXI.v`（那是 AXI 顶层，第三部分最后才看）
4. Add Simulation Sources：把 `tb\` 下的 3 个 `tb_*.v` 加进去
5. 左侧 Flow Navigator → Run Simulation → Run Behavioral Simulation
6. 在 Simulation Sources 里选中某个 tb（如 `tb_ecg_detect`）→ 右键 Set as Top → 再跑
7. 波形窗口：把 `ecg_wave / sample_tick / above / r_detect / rr_count` 加进去观察

**看懂顶层后**：再把 `rtl\ecg_axi.v` 和 `ecg_axi_slave_lite_v1_0_S00_AXI.v` 加进工程**读一读**（不用仿真，看结构即可）。

**（可选）完整 Block Design**：如果组长把整个 `ecg_system` 工程发给你，打开 `ecg_system.xpr`，左侧 Sources 里双击 **Block Design**（`ecg_bd`）——能看到 PS7、AXI Interconnect、我们的 `ecg_axi_0` IP 是怎么连起来的。**这一步只是"看结构"，不要改任何东西。**

---

# 第五部分：习惯


## 1. 用好 AI（问答+干活）
问问题全面深入，多追问；命令干活提要求明确，注意安全
保持反思质疑，多提醒ai检查验证

##2. 善于找资源
b站看课程，xhs看攻略，github看教程，各种网站多搜多找

## 3. 多总结留痕
学完一阶段让ai总结，明确干了什么；各阶段学习资料生成文档保存

##4.不要偷懒啊，时间不多啦

---


