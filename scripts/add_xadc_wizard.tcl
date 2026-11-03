# =============================================================================
#  add_xadc_wizard.tcl  ——  在 ecg_bd 里加入 XADC Wizard（D1 任务）
#  用法：在 Vivado 的 Tcl Console 里【逐段】粘贴（每段看完输出再粘下一段）
#  前提：Vivado 已打开工程 D:\ecg\vivado\ecg_system\ecg_system.xpr
#  作者注：所有参数值均取自 Vivado 2026.1 自带 IP 定义 component.xml
#          （xadc_wiz_v3_3），不是猜的。
# =============================================================================

# -----------------------------------------------------------------------------
# 第 0 段：安全网 —— 把当前 BD 导出成 Tcl 脚本（万一改坏可回滚）
# -----------------------------------------------------------------------------
write_bd_tcl -force D:/ecg/_backup/ecg_bd_before_xadc.tcl
# 说明：write_bd_tcl = 把整个 Block Design 的全部内容（cell/连线/地址）
#       导出成一份可重新执行的 Tcl 脚本。-force = 文件已存在时覆盖。

# -----------------------------------------------------------------------------
# 第 1 段：确认 BD 已打开，并新建 XADC Wizard
# -----------------------------------------------------------------------------
current_bd_design
# 说明：current_bd_design 打印当前打开的 BD 名字。
#       若报错 "no current design"，先执行下面这行再继续：
#       open_bd_design [get_files ecg_bd.bd]

create_bd_cell -type ip -vlnv xilinx.com:ip:xadc_wiz:3.3 xadc_wiz_0
# 说明：create_bd_cell = 在 BD 里新建一个 cell（方块）。
#   -type ip    ：类型是 IP（而不是 module / hierarchical 等）
#   -vlnv       ：Vendor:Library:Name:Version 四段式 IP 编号
#                 xilinx.com : ip : xadc_wiz : 3.3
#   xadc_wiz_0  ：我给这个实例起的名字（后面都用这个名字引用它）

# -----------------------------------------------------------------------------
# 第 2 段：配置 IP —— 接口用 AXI4-Lite，序列器连续扫描内部通道
# -----------------------------------------------------------------------------
set_property -dict [list \
    CONFIG.INTERFACE_SELECTION      {Enable_AXI}          \
    CONFIG.XADC_STARUP_SELECTION    {channel_sequencer}   \
    CONFIG.SEQUENCER_MODE           {Continuous}          \
    CONFIG.CHANNEL_ENABLE_TEMPERATURE {true}              \
    CONFIG.CHANNEL_ENABLE_VCCINT      {true}              \
    CONFIG.CHANNEL_ENABLE_VCCAUX      {true}              \
] [get_bd_cells xadc_wiz_0]
# 说明：set_property = 给对象设置属性。
#   -dict [list ...] ：一次性设置多组"属性名 值"（比写多行 set_property 快）
#   CONFIG.xxx       ：BD 里 IP 的配置参数都以 CONFIG. 开头
#   [get_bd_cells xadc_wiz_0] ：作用对象 = 刚才建的那个 cell
# 各参数含义：
#   INTERFACE_SELECTION=Enable_AXI   界面显示为 "AXI4Lite"；改用 CPU 可访问的寄存器接口
#                                    （另两个可选值：ENABLE_DRP=纯DRP口、None=不用）
#   XADC_STARUP_SELECTION=channel_sequencer  开机后走"通道序列器"模式
#   SEQUENCER_MODE=Continuous        序列器连续不停地轮转（不是只扫一遍）
#   CHANNEL_ENABLE_TEMPERATURE      把"芯片温度"加入扫描队列
#   CHANNEL_ENABLE_VCCINT           把"内核电压 1.0V"加入扫描队列
#   CHANNEL_ENABLE_VCCAUX           把"辅助电压 1.8V"加入扫描队列
# 注意：V_P/V_N（J5 排针那路模拟输入）本轮【故意不开】——
#       它需要接外部模拟引脚，等 D3 接了 AD8232 再开，避免这次构建多一个变量。

# -----------------------------------------------------------------------------
# 第 3 段：接线 —— AXI 总线 + 时钟 + 复位
# -----------------------------------------------------------------------------
set cur_mi [get_property CONFIG.NUM_MI [get_bd_cells ps7_axi_periph]]
set new_mi [expr {$cur_mi + 1}]
set_property -dict [list CONFIG.NUM_MI $new_mi] [get_bd_cells ps7_axi_periph]
puts "AXI 互连主机端口数：$cur_mi -> $new_mi"
# 说明：现有 AXI 互连 ps7_axi_periph 原本只带 1 个从机（我们的 ecg_axi_0）。
#       再加一个从机就必须给它多开一个"主机端口"。
#   get_property CONFIG.NUM_MI ... = 读出当前端口数（记为 cur_mi）
#   expr {$cur_mi + 1}             = 算术加一（Tcl 里算数必须用 expr）
#   puts "..."                     = 打印一行提示，便于确认
# 执行后互连上会多出一个 M01_AXI 端口（原来的是 M00_AXI）。

connect_bd_intf_net [get_bd_intf_pins ps7_axi_periph/M01_AXI] \
                    [get_bd_intf_pins xadc_wiz_0/s_axi_lite]
# 说明：connect_bd_intf_net = 连接"接口"（一组信号线，如整个 AXI 总线）。
#   intf_pins = interface pin（接口端点）。这里把互连的新主机口
#   接到 XADC 的 AXI 从机口 s_axi_lite 上。

connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ps7_axi_periph/M01_ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins xadc_wiz_0/s_axi_aclk]
# 说明：connect_bd_net = 连接"单根信号线"。
#   第一行：把 PS 输出的 FCLK_CLK0（100MHz）接到互连新端口的时钟脚；
#   第二行：同一路时钟也接到 XADC 的 AXI 时钟脚。
#   （AXI 规定：互连的每个主机端口和它挂的从机必须同源同频时钟）

connect_bd_net [get_bd_pins rst_ps7_50M/peripheral_aresetn] [get_bd_pins ps7_axi_periph/M01_ARESETN]
connect_bd_net [get_bd_pins rst_ps7_50M/peripheral_aresetn] [get_bd_pins xadc_wiz_0/s_axi_aresetn]
# 说明：复位同理。peripheral_aresetn 是"外设复位、低电平有效"（名字末尾 n = active low）。
#   复用已有的复位模块 rst_ps7_50M，不新建。

# 保险：若该配置下 IP 仍带 dclk_in（DRP 时钟）脚，就一并接上
if {[llength [get_bd_pins -quiet xadc_wiz_0/dclk_in]] > 0} {
    connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins xadc_wiz_0/dclk_in]
    puts "已连接 dclk_in"
} else {
    puts "该配置无 dclk_in 端口（AXI 模式下时钟由 s_axi_aclk 提供）"
}
# 说明：get_bd_pins -quiet = 查不到时不报错、返回空；
#       llength = 数元素个数。这是"先探测再连接"的写法，避免脚本中断。

# -----------------------------------------------------------------------------
# 第 4 段：分配地址并打印出来（脚本要用这个地址！）
# -----------------------------------------------------------------------------
assign_bd_address
# 说明：assign_bd_address = 自动给所有还没分配地址的从机分配一段地址空间。

foreach s [get_bd_addr_segs -of_objects [get_bd_cells xadc_wiz_0]] {
    puts "★ XADC 地址段: $s   offset=[get_property offset $s]  range=[get_property range $s]"
}
# 说明：get_bd_addr_segs = 取出地址段对象；-of_objects 限定只属于 xadc_wiz_0 的。
#       foreach = 逐个遍历并打印 offset（基地址）与 range（长度）。
# ★ 请把打印出来的 offset 记下来（预期 0x43C10000），
#   它就是 xadc_selftest.py 里的 DEFAULT_BASE。

# -----------------------------------------------------------------------------
# 第 5 段：校验 + 保存
# -----------------------------------------------------------------------------
validate_bd_design
save_bd_design
# 说明：validate_bd_design = 检查 BD 是否有未连接/冲突（必须无 error）。
#       save_bd_design   = 保存这个 BD。

# -----------------------------------------------------------------------------
# 第 6 段：重新生成 BD 产物（改动后必须做）
# -----------------------------------------------------------------------------
reset_target all [get_files ecg_bd.bd]
generate_target all [get_files ecg_bd.bd]
# 说明：reset_target   = 清掉 BD 之前生成的产物（wrapper/HDL 等），
#       generate_target= 按新 BD 重新生成。这一步就是协作约定里的 G1/G2 纪律。

# -----------------------------------------------------------------------------
# 第 7 段：跑综合+实现+出比特流（约 15~20 分钟）
# -----------------------------------------------------------------------------
reset_run synth_1
reset_run impl_1
# 说明：★ 必须先重置！上一次构建已把 impl_1 跑完并写了比特流，设计改动后
#       Vivado 会报 [Vivado 12-1088] Step 'write_bitstream' needs to be reset
#       before launching —— 这不是设计错误，是"已完成步骤不许直接重跑"的保护机制。
#       reset_run = 把该运行的步骤状态/结果清空，回到 Not started。
#       （错误信息里提到的 -prev_step / -from_step 可只重置部分步骤，
#         但整条重置最简单、最不易再出错，本次反正要全部重跑。）

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
# 说明：launch_runs = 启动一个运行（run）。impl_1 是实现运行；
#         -to_step write_bitstream = 一直做到"写比特流"这一步（会自动先综合）；
#         -jobs 4 = 用 4 个线程并行，快一些。
#       wait_on_run = 阻塞等待它跑完，跑完 Tcl Console 才继续。

get_property STATUS   [get_runs impl_1]
get_property PROGRESS [get_runs impl_1]
# 说明：跑完后的验收 —— 期望看到 "write_bitstream Complete" 与 "100%"。
#       比特流位置：ecg_system.runs\impl_1\ecg_bd_wrapper.bit