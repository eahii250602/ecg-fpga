# =====================================================================
# ECG-DDS-FPGA  ·  D1  ·  XADC Wizard 加入 BD "ecg_bd"
# 用法: 打开 ecg_system.xpr 与 BD ecg_bd 后, 在 Vivado Tcl Console
#       按 STEP 1 / STEP 2 / STEP 3 分段粘贴执行(每段之间核对输出)。
# 归档位置建议: D:\ecg\vivado\d1_add_xadc_to_bd.tcl
# 前提: BD "ecg_bd" 已在 Vivado GUI 画布中打开。
# 依据: 全部 CONFIG 参数名/取值核对自
#       E:\vivado\2026.1\Vivado\data\ip\xilinx\xadc_wiz_v3_3\component.xml
#       (IP 版本 3.3 见其 L6; 参数定义 L4023-4740; 合法取值 L3630-3726;
#        BD 内自动选 AXI 的官方写法见同目录 bd\bd.tcl L46-49)
# 实例/网名核对自 ecg_bd.bd: ps7(L207) ecg_axi_0(L1381)
#       ps7_axi_periph(L1389, NUM_MI=1 见 L1395) rst_ps7_50M(L1646)
#       网 ps7_FCLK_CLK0(L1682) rst_ps7_50M_peripheral_aresetn(L1699)
# =====================================================================

# ============================ STEP 1 ================================
# 添加 XADC Wizard 并配置:
#   AXI4-Lite 接口 + 通道序列器(Continuous) + 温度/VCCINT/VCCAUX 勾选

if {[catch {current_bd_design} bd]} {
    error "No block design is open. Open ecg_bd in the GUI first, then paste STEP 1."
}
puts "D1 STEP1: current block design = $bd"

if {[llength [get_bd_cells -quiet xadc_wiz_0]] != 0} {
    error "xadc_wiz_0 already exists. To redo: select it in the GUI, press Delete, paste again."
}

create_bd_cell -type ip -vlnv xilinx.com:ip:xadc_wiz:3.3 xadc_wiz_0

set_property -dict [list \
    CONFIG.INTERFACE_SELECTION          {Enable_AXI} \
    CONFIG.XADC_STARUP_SELECTION        {channel_sequencer} \
    CONFIG.STARTUP_CHANNEL_SELECTION    {channel_sequencer} \
    CONFIG.SEQUENCER_MODE               {Continuous} \
    CONFIG.TIMING_MODE                  {Continuous} \
    CONFIG.DCLK_FREQUENCY               {100.0} \
    CONFIG.CHANNEL_ENABLE_TEMPERATURE   {true} \
    CONFIG.CHANNEL_ENABLE_VCCINT        {true} \
    CONFIG.CHANNEL_ENABLE_VCCAUX        {true} \
    CONFIG.CHANNEL_ENABLE_VP_VN         {true} \
    CONFIG.CHANNEL_ENABLE_VAUXP0_VAUXN0 {true} \
] [get_bd_cells xadc_wiz_0]

puts "==== XADC config readback ===="
foreach p {INTERFACE_SELECTION XADC_STARUP_SELECTION STARTUP_CHANNEL_SELECTION \
           SEQUENCER_MODE TIMING_MODE DCLK_FREQUENCY \
           CHANNEL_ENABLE_TEMPERATURE CHANNEL_ENABLE_VCCINT CHANNEL_ENABLE_VCCAUX \
           CHANNEL_ENABLE_VP_VN CHANNEL_ENABLE_VAUXP0_VAUXN0} {
    puts [format "  %-34s = %s" $p [get_property CONFIG.$p [get_bd_cells xadc_wiz_0]]]
}
puts "==== readback done: paste this block back to the AI ===="

# ============================ STEP 2 ================================
# 接线(等价 GUI 的 Run Connection Automation) + 自动分配基地址
# 注意: 若某条报 already connected 之类错误, 多半是该步已做过, 跳过即可

set_property -dict [list CONFIG.NUM_MI {2}] [get_bd_cells ps7_axi_periph]

connect_bd_intf_net \
    [get_bd_intf_pins ps7_axi_periph/M01_AXI] \
    [get_bd_intf_pins xadc_wiz_0/s_axi_lite]

connect_bd_net -net ps7_FCLK_CLK0 \
    [get_bd_pins ps7_axi_periph/M01_ACLK] \
    [get_bd_pins xadc_wiz_0/s_axi_aclk]

connect_bd_net -net rst_ps7_50M_peripheral_aresetn \
    [get_bd_pins ps7_axi_periph/M01_ARESETN] \
    [get_bd_pins xadc_wiz_0/s_axi_aresetn]

assign_bd_address

# Vivado 2026.1 已无 report_bd_address 命令, 用 get_bd_addr_segs 循环代替
puts "==== BD address map ===="
foreach seg [get_bd_addr_segs -quiet] {
    set off [get_property -quiet OFFSET $seg]
    set rng [get_property -quiet RANGE $seg]
    puts [format "  %-56s offset=%s  range=%s" $seg $off $rng]
}
puts "==== address map done: paste this back (expect XADC at 0x43C10000) ===="

# ============================ STEP 3 ================================
# 校验 + 保存 (等价 GUI 的 F6 + Ctrl-S)
# intr 中断脚/模拟脚未接会产生 WARNING, 属预期(本项目纯轮询, 不用中断)

validate_bd_design
save_bd_design

# ============================ STEP 4 (可选) ==========================
# 重建 BD 输出产物并生成比特流(~15 分钟), 对应 HANDOFF 7.1 第 4 步
# 产物: D:\ecg\vivado\ecg_system\ecg_system.runs\impl_1\ecg_bd.bit + .hwh
# 确认 STEP 3 校验通过后再执行: 去掉下面 4 行行首的 "#"

# reset_target all [get_files ecg_bd.bd]
# generate_target all [get_files ecg_bd.bd]
# launch_runs impl_1 -to_step write_bitstream -jobs 4
# wait_on_run impl_1
