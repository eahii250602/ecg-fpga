# 已知隐患清单（Landmines）

> **本文档与 `skill/pitfalls.md` 的分工**：
> - `skill/pitfalls.md` = **已经踩过**的坑（有事故记录、有教训）
> - `report/landmines.md` = **还没爆**的隐患（预防性清单）
>
> **维护方式**：由助手在每次归档时机主动更新。
> **最后更新**：2026-10-23（rr_count 根因破案：新增 **L-15**；L-13/L-14 板上现象确认）

---

# 一、🔴 高危：一旦踩中会**静默失效**（不报错，功能全错）

## L-01 ⭐ 同一个 HDL 在磁盘上有 **7 份副本**，只有 **1 份生效**

**这是本项目最大的地雷。**

```
   ★ 唯一生效的位置：
      D:\ecg\ip_repo\ecg_axi_1_0\hdl\*.v        （7 个文件）
              ↓ Vivado 在生成产物时【复制】到工程里
      D:\ecg\vivado\ecg_system\ecg_system.gen\...\ipshared\<hash>\hdl\*.v
      D:\ecg\vivado\ecg_system\ecg_system.ip_user_files\...\ipshared\<hash>\hdl\*.v
```

### 全部副本关系表（**修文件前必须查这张表**）

| # | 路径 | 是否生效 | 谁在用 |
|---|---|---|---|
| **1** | `D:\ecg\ip_repo\ecg_axi_1_0\hdl\*.v` | ✅ **唯一真源** | `ecg_system` 工程（经上面两个副本间接使用） |
| 2 | `D:\ecg\ip_repo\ecg_axi_1_0\component.xml` | ✅ 生效 | Vivado 识别 IP 的"身份证" |
| 3 | `ecg_system.gen\...\ipshared\<hash>\hdl\*.v` | ⚠️ 自动副本（**勿手改**） | 综合时实际读的文件 |
| 4 | `ecg_system.ip_user_files\...\ipshared\<hash>\hdl\*.v` | ⚠️ 自动副本（**勿手改**） | 导出/仿真用 |
| 5 | `D:\ecg\vivado_src\*.v` | ❌ **已不生效** | 仅作为备份/母版；`tb_*.v` 测试台仍在用 |
| 6 | `D:\ecg\ip_repo\edit_ecg_axi_v1_0.srcs\...\imports\vivado_src\*.v` | ❌ **已废弃** | 无（自包含化后 `component.xml` 不再引用） |
| 7 | `D:\ecg\vivado\dds_ecg_sim\...\imports\vivado_src\*.v` | ✅ **仅对仿真工程生效** | `dds_ecg_sim` 仿真工程 |
| 8 | `D:\ecg\_backup\ip_repo_20261007\...` | 备份 | 出事时的回退源 |
| 9 | `D:\ecg\_work\ecg_rom_memfile_backup.v` | 备份 | `$readmemh` 版原文件 |

### ⚠️ 危险场景

```
   场景：队友（或未来的你）想改 DDS 的心率范围
        ↓
   他打开 D:\ecg\vivado_src\dds_ecg.v 改了
        ↓
   ★ 综合结果【毫无变化】——不报错、不警告
        ↓
   他会以为"改错了"，然后反复尝试 → 浪费几小时
```

### 处理方案

| 优先 | 措施 |
|---|---|
| **⭐ 立即** | **在废弃副本目录放一张"此目录已废弃"的说明文件**（见 §五 待办） |
| 长期 | 竞赛提交包只保留 `src/rtl/` 一份，其余不打包 |
| 习惯 | **改任何 HDL 前，先查本文档 §一 L-01 的表** |

---

## L-02 IP 源码里仍留有**本机绝对路径**（虽已不生效，但不干净）

| 项 | 内容 |
|---|---|
| **位置** | `D:\ecg\ip_repo\ecg_axi_1_0\hdl\dds_ecg.v` 第 13 行<br>`parameter MEM_FILE = "D:/ecg/vivado_src/ecg_256x12.mem"` |
| **当前影响** | ✅ **无**——`ecg_rom.v` 已改为内嵌数据版，**忽略** `MEM_FILE` 参数 |
| **潜在风险** | ① 竞赛"可复现性"评分上不干净（IP 源码带本机路径）<br>② 若日后把 `ecg_rom.v` 换回 `$readmemh` 版，该路径会**立即生效** → 换机器必崩 |
| **处理** | 把默认值改成无害的相对字符串（如 `"ecg_256x12.mem"`）——**但修改 IP 源码需走规则 G1 的强制重建流程**，建议与其他改动**批处理**，避免反复重综合 |

---

## L-03 Vivado IP 缓存不同步

**详见 `working_agreement.md` §3.5**（规则 G1、G2）

```
   改完 IP 源码后重新综合，Vivado 可能仍使用 .gen 里的【旧副本】
   → 必须：关工程 → 完全退出 Vivado → 删 <project>.gen → 重开 → 再综合
   → 且综合前先核对缓存副本的时间戳与内容（规则 G2）
```

---

## L-04 `component.xml` 里只有部分文件带校验值

```
   带校验值（改动能被 Vivado 察觉）：hdl/ecg_axi.v、hdl/tick_gen.v
   不带校验值（改动【不能】被察觉）：其余 5 个
        ↓
   机制未证实（见 §3.5"已知疑点"），故一律执行规则 G1
```

---

## L-13 ⭐⭐⭐ `Clocks.fclk0_mhz` 会把 PL 超频到 160 MHz（**2026-10-23 新增**）

**这是第二个"静默失效"级地雷，比 L-03 更隐蔽。**

```
   触发代码（只要出现就危险）：
       from pynq import Clocks
       Clocks.fclk0_mhz = 100       # ← 绝对不要写！

   ★ 为什么危险：
      · .hwh 里 IO PLL = 1600 MHz，FCLK0 分频 4×4 = 16 → 实际就是 100 MHz
      · PYNQ 的 Clocks 类按【1000 MHz】的 PLL 基准算
        → 读出来显示 62.5 MHz（纯显示 bug，不是真实频率）
      · 一旦 setter 被调用：PYNQ 算分频 = 1000/100 = 10
        → 真实频率 = 1600/10 = 160 MHz → PL 被超频 60%
        → 采样率从 250 Hz 变成 400 Hz、时序可能不收敛、随机故障

   ★ 正确做法：什么都不做。overlay 加载时 .hwh 的时钟配置已生效。
   ★ 用 rr_count 反推验证真实时钟（唯一可信的检查方式）：
         rr_count ≈ 250 × 60 / BPM      （72 BPM → 约 208）
         明显偏离理论值 → 说明 FCLK0 不是 100 MHz
```

**已处理**：`board\python\ecg_monitor_serial.py` 里的该调用已于 2026-10-23 删除（改为注释说明）。

---

## L-15 ⭐⭐⭐ IP 参数被包装层当【字符串】传给 RTL（2026-10-23 破案，静默失效）

**这是第三个"静默失效"级地雷，也是 rr_count 之谜（51/104 vs 206）的总根因。**

```
   现象：板上 rr_count = 51 / 104（理论 206.5）；波形/AXI/版本号全部正常
         → 表现为"心率测出 294 BPM"，不报任何错。

   根因链（三层，每层都正常、合起来才炸）：
     ① ecg_axi.v 声明 parameter signed [11:0] THRESHOLD = 12'sd1200
        → IP 打包器归为「向量型」：component.xml 里 dataType="signed(11 0)"
     ② THRESHOLD 的两个 value 都缺 spirit:format="long"（其它参数有）
        → BD 包装层把值渲染成字符串：.THRESHOLD("1200")
     ③ Verilog 字符串=位向量："1200" = 32'h31323030
        → 赋给 12 位参数时截断低 12 位 = 0x030 = ★ 48 ★
        → 硬件实际执行 ecg_wave > 48 → P波/QRS/T波全部超阈值
        → 每拍 3 次检测 → rr_count 循环 {51, 51, 104}（和恰=206.5）

   为什么历次仿真都没抓到：
     所有测试台都【直接例化 ecg_axi 传数值参数】，恰好绕过了
     「BD 包装层 → 比特流」这条路径 —— bug 只住在那里。

   ★ 修复（2026-10-23 完成，**板上验证通过**）：
     ① HDL：`parameter signed [11:0] THRESHOLD` → `parameter integer THRESHOLD = 1200`
        （Vivado 按 HDL 声明推导参数类型：带位宽/signed → 向量型 → 值加引号）
     ② XCI（BD 里 IP 实例的配置文件 `*.xci`）两处 THRESHOLD 补 `"format": "long"`
        —— 这是包装层渲染成数字的【直接开关】；XCI 创建后从不自动重写，
        所以 10-07 的错误一直留到了 10-23（本案的真正载体）
     ③ component.xml 同步改成 integer（保持一致，防止以后重新打包再犯）
     ④ 验证顺序：grep 包装层无引号 → G2 md5 门 → 综合 → 板上实测

   ★ 板上验证结果（2026-10-23 21:5x）：
        rr_count = 207（理论 206.5，差 0.2%）→ BPM 72.46（修复前 51 → 294.12）
        fix_test S14 读到的 80 = 启动瞬态（复位到第一个 R 峰的 tick 数），非 bug

   ★ 规则（以后必须遵守）：
     a. IP 顶层可配置参数一律声明 `parameter integer`（不带位宽/signed）；
     b. 改 IP 参数后必须检查【三处】：HDL 声明、component.xml、XCI 的 format 字段；
     c. 重建前 grep synth 包装层，确认所有参数值【不带引号】（加入 G2 验证门）。
```

---

# 二、🟡 中危：会报错或现象明显

## L-05 `.bit` 与 `.hwh` **必须同名**，否则 PYNQ 找不到地址

```
   Overlay('ecg_bd.bit') 会自动去找同名的 ecg_bd.hwh
        ↓
   而 Vivado 生成的是 ecg_bd_wrapper.bit + ecg_bd.hwh（同名！）
        ↓
   ★ 复制到板子前必须把 .bit 改名为 ecg_bd.bit
   ★ 归档目录 D:\ecg\board\bit\ 已经做好配对
```

## L-06 设计一改动，`impl_1` 运行目录会被清空

```
   表现：比特流 / routed.dcp / 完成标记 全部消失
   原因：Vivado 判定"实现结果已失效"（正常行为）
   ★ 所以【里程碑构建必须立刻归档 .bit + .hwh】（规则 G4）
```

## L-07 当前是**内联综合**：改任何 IP 源码都要全设计重综合

```
   现状：.runs 下没有 OOC 运行目录 → 全局（内联）综合
   影响：改动后不能只重综合某个 IP，必须整设计重跑（本设计约 1 分钟，可接受）
   ★ 副作用：资源数字与"OOC 时代"（V3）不可直接比较（见 design_decisions.md 勘误 E-02）
```

## L-08 手工编辑 `component.xml` 会被 Vivado 覆盖

```
   IP 元数据由 Vivado 管理，工程保存/关闭时会用内存模型回写
   ★ 必须通过 IP 打包器维护；或确保 Vivado 【已完全退出】时再改
   （2026-10-07 曾踩过：手改的文件登记项在关闭工程后消失）
```

---

# 三、🟢 低危 / 已处理（知晓即可）

| # | 隐患 | 状态 |
|---|---|---|
| **L-09** | IP 依赖 `edit_ecg_axi_v1_0.srcs\`（删了会崩工程） | ✅ **已修复**（5 个文件已移入 IP 自己的 `hdl\`，`component.xml` 路径已改） |
| **L-10** | WHS（保持时间余量）仅 **+0.012 ns** | ⚠️ 仍为正当（THS=0，无违例），但**余量很薄**；后续加逻辑要复查 |
| **L-11** | `hdl/ecg_256x12.mem` 已不再被使用（数据已内嵌进 `ecg_rom.v`） | 🟢 保留作参考；**不要再以为改它能改变波形** |
| **L-12** | `ecg_system` 用 AXI Interconnect，练习工程用 SmartConnect | 🟢 历史遗留，两者功能等价；练习工程已删除 |

---

## L-14 AXI 写握手的「通道顺序」死锁（2026-10-11 已修复，**教训要记住**）

```
   现象：板上任何 AXI 写操作 → 整机冻死（读完全正常，键盘无响应）
   根因：老式 Idle/Waddr/Wdata 状态机 + wready 复位后常高。
         W 先于 AW 到达时（AXI 规范允许两通道无顺序约束），
         W 握手被提前单独消费 → 状态机进 Wdata 等一个永不出现的 WVALID
         → BVALID 永不置位 → CPU 永远等写响应 → 冻死。
   修复：awready/wready 只在 AWVALID && WVALID【同时】有效时脉冲一拍；
         寄存器写入改由 slv_reg_wren（完整握手拍）驱动，地址只用锁存值。
         文件：ip_repo\ecg_axi_1_0\hdl\ecg_axi_slave_lite_v1_0_S00_AXI.v

   ★★★ 教训（比 bug 本身重要）：
     协议测试台必须覆盖【所有合法输入顺序】，不能只测"同时到达"。
     8/8 全过 ≠ 写通道没问题 —— 覆盖不到的合法场景就是定时炸弹。
     本次复现只花了 10 分钟：扩展测试台加一条 W-first 用例即可。

   现状：修复版仿真 12/12 通过（含 W-first）；2026-10-23 **板上确认**
         （fix_test S7~S13：版本号 0xEC600001 / 默认 FTW=52 / 写读回环全过）。
```

---

# 四、⭐ 一句话防雷口诀

```
   ① 改 HDL 之前 —— 先查 L-01 的表，认准【唯一真源】
   ② 改完 IP 源码 —— 走 G1（删 .gen 强制重建）+ G2（先验缓存再综合）
   ③ 里程碑完成  —— 归档 .bit + .hwh（G4），别只归档报告
   ④ 报数字之前  —— 先说清"来自哪个工程的哪份报告、哪个阶段（综合/实现）"
   ⑤ 出问题排查  —— 优先看【工具日志】（综合/DRC/时序），人工判断会出错
   ⑥ 动 PYNQ 时钟 —— 绝对不要碰 Clocks.fclk0_mhz（L-13，会超频到 160MHz）
   ⑦ 写协议测试  —— 必须覆盖所有合法输入顺序，尤其"W 先于 AW"（L-14）
   ⑧ 上板之前    —— 先仿真复现板上症状，别再靠猜（这条是 L-14 换来的）
   ⑨ 查 IP 参数  —— 包装层里值带引号 = 字符串截断（L-15，rr_count 根因）
```

---

# 五、待办清理清单

| 优先 | 事项 | 说明 |
|---|---|---|
| **高** | 在废弃副本目录放**说明文件** | `D:\ecg\vivado_src\` 与 `D:\ecg\ip_repo\edit_ecg_axi_v1_0.srcs\` 各放一份"此目录已废弃，真源在 ip_repo\ecg_axi_1_0\hdl\" |
| 中 | 清理 `dds_ecg.v` 的绝对路径（L-02） | 建议与后续 HDL 改动批处理，避免反复重综合 |
| 中 | 竞赛提交包只保留一份源码 | 避免打包进 7 份副本 |
| 低 | 统一 `vivado_src\` 与仿真工程副本 | 或明确标注各自用途 |
| 低 | 复查 WHS 余量（L-10） | 后续加逻辑时一并看 |
