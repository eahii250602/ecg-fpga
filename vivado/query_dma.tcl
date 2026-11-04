open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
open_bd_design [get_files ecg_bd.bd]
puts "==DMA CONFIG=="
foreach p {CONFIG.c_include_s2mm CONFIG.c_s_axis_s2mm_tdata_width CONFIG.c_m_axi_s2mm_data_width CONFIG.c_sg_length_width} {
  catch { puts "  $p = [get_property $p [get_bd_cells axi_dma_0]]" } e
}
puts "==PC CONFIG=="
foreach p {CONFIG.SI_PROTOCOL CONFIG.MI_PROTOCOL CONFIG.SI_DATA_WIDTH CONFIG.MI_DATA_WIDTH} {
  catch { puts "  $p = [get_property $p [get_bd_cells axi_pc_0]]" } e
}
puts "==PS HP0=="
catch { puts "  WIDTH = [get_property CONFIG.PCW_S_AXI_HP0_DATA_WIDTH [get_bd_cells ps7]]" } e
puts "==AXIS IF PINS=="
foreach p [get_bd_intf_pins -of_objects [get_bd_cells axi_dma_0]] { puts "  $p" }