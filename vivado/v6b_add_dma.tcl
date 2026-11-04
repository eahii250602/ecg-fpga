open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
open_bd_design [get_files ecg_bd.bd]
set fails 0
set_property -dict [list CONFIG.PCW_USE_S_AXI_HP0 {1} CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {32}] [get_bd_cells ps7]
set rc [catch { create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0 } e]
set rc [catch { set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_include_mm2s {0} CONFIG.c_include_s2mm {1} CONFIG.c_m_axi_s2mm_data_width {32} CONFIG.c_s_axis_s2mm_tdata_width {16}] [get_bd_cells axi_dma_0] } e]
set rc [catch { create_bd_cell -type ip -vlnv xilinx.com:ip:axi_protocol_converter:2.1 axi_pc_0 } e]
set rc [catch { set_property -dict [list CONFIG.MI_PROTOCOL {AXI3} CONFIG.SI_PROTOCOL {AXI4}] [get_bd_cells axi_pc_0] } e]
set_property -dict [list CONFIG.NUM_MI {3}] [get_bd_cells ps7_axi_periph]
set rc [catch { connect_bd_intf_net [get_bd_intf_pins ps7_axi_periph/M02_AXI] [get_bd_intf_pins axi_dma_0/S_AXI_LITE] } e]
set rc [catch { connect_bd_intf_net [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM] [get_bd_intf_pins ecg_axi_0/M_AXIS] } e]
set rc [catch { connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXI_S2MM] [get_bd_intf_pins axi_pc_0/S_AXI] } e]
set rc [catch { connect_bd_intf_net [get_bd_intf_pins axi_pc_0/M_AXI] [get_bd_intf_pins ps7/S_AXI_HP0] } e]
puts "### CONNECT DONE"
set rc [catch { connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_dma_0/s_axi_lite_aclk] [get_bd_pins axi_dma_0/m_axi_s2mm_aclk] [get_bd_pins axi_pc_0/aclk] [get_bd_pins ps7/S_AXI_HP0_ACLK] [get_bd_pins ps7_axi_periph/M02_ACLK] } e]
puts "### CLK rc=$rc $e"
set rc [catch { connect_bd_net [get_bd_pins rst_ps7_50M/peripheral_aresetn] [get_bd_pins axi_dma_0/axi_resetn] [get_bd_pins axi_pc_0/aresetn] [get_bd_pins ps7_axi_periph/M02_ARESETN] } e]
puts "### RST rc=$rc $e"
set rc [catch { assign_bd_address } e]
puts "### ADDR rc=$rc"
set rc [catch { validate_bd_design } ev]
puts "### VALIDATE rc=$rc $ev"
if {$rc == 0} { save_bd_design; puts "### SAVED OK" }