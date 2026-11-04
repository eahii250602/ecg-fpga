open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
open_bd_design [get_files ecg_bd.bd]

# ---- 1. 使能 PS 的 HP0 从口（DMA 写 DDR 用）----
set_property -dict [list CONFIG.PCW_USE_S_AXI_HP0 {1}] [get_bd_cells ps7]
puts "==PS INTF=="
foreach i [get_bd_intf_pins -of_objects [get_bd_cells ps7]] { puts "  $i" }

# ---- 2. 加 AXI DMA ----
if {[llength [get_bd_cells -quiet axi_dma_0]] == 0} {
    create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0
    set_property -dict [list \
        CONFIG.c_include_sg               {0} \
        CONFIG.c_include_mm2s             {0} \
        CONFIG.c_include_s2mm             {1} \
        CONFIG.c_m_axi_s2mm_data_width    {32} \
        CONFIG.c_s_axis_s2mm_tdata_width  {16} \
    ] [get_bd_cells axi_dma_0]
}
puts "==DMA PINS=="
foreach p [get_bd_pins -of_objects [get_bd_cells axi_dma_0]] {
  if {[string match *clk* $p] || [string match *resetn* $p]} { puts "  $p" }
}
puts "==DMA INTF=="
foreach i [get_bd_intf_pins -of_objects [get_bd_cells axi_dma_0]] { puts "  $i" }

# ---- 3. 连线 ----
set_property -dict [list CONFIG.NUM_MI {3}] [get_bd_cells ps7_axi_periph]
set fails 0
foreach c {
 {ps7_axi_periph/M02_AXI   axi_dma_0/S_AXI_LITE}
 {axi_dma_0/M_AXI_S2MM     ps7/S_AXI_HP0}
 {axi_dma_0/S_AXIS_S2MM    ecg_axi_0/M_AXIS}
} {
  set a [lindex $c 0]; set b [lindex $c 1]
  if {[catch { connect_bd_intf_net [get_bd_intf_pins $a] [get_bd_intf_pins $b] } e]} {
     puts "### CONNECT FAIL $a -> $b : $e"; incr fails
  } else { puts "### CONNECT OK $a -> $b" }
}
if {[catch {
  connect_bd_net [get_bd_nets ps7_FCLK_CLK0] \
    [get_bd_pins axi_dma_0/s_axi_lite_aclk] \
    [get_bd_pins axi_dma_0/m_axi_s2mm_aclk] \
    [get_bd_pins axi_dma_0/s_axis_s2mm_aclk] \
    [get_bd_pins ps7/S_AXI_HP0_ACLK] \
    [get_bd_pins ps7_axi_periph/M02_ACLK]
} e]} { puts "### CLK FAIL $e"; incr fails }
if {[catch {
  connect_bd_net [get_bd_nets rst_ps7_50M_peripheral_aresetn] \
    [get_bd_pins axi_dma_0/axi_resetn] \
    [get_bd_pins ps7_axi_periph/M02_ARESETN]
} e]} { puts "### RST FAIL $e"; incr fails }

# ---- 4. 地址 + 校验（失败不保存）----
if {[catch { assign_bd_address } e]} { puts "### ADDR FAIL $e"; incr fails }
foreach seg [get_bd_addr_segs -quiet] {
  set o [get_property -quiet OFFSET $seg]
  if {$o ne ""} { puts "  SEG $seg offset=$o" }
}
set rc [catch { validate_bd_design } ev]
if {$rc == 0 && $fails == 0} {
    save_bd_design
    puts "### SAVED (validate OK, fails=$fails)"
} else {
    puts "### NOT SAVED  validate_rc=$rc fails=$fails : $ev"
}