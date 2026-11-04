open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
open_bd_design [get_files ecg_bd.bd]
puts "==PS7 INTF=="
foreach i [get_bd_intf_pins -of_objects [get_bd_cells ps7]] { puts "  $i" }
puts "==HP 配置=="
foreach p {CONFIG.PCW_USE_S_AXI_HP0 CONFIG.PCW_USE_S_AXI_HP1 CONFIG.PCW_USE_S_AXI_GP0 CONFIG.PCW_USE_S_AXI_GP1} {
  catch { puts "  $p = [get_property $p [get_bd_cells ps7]]" } e
}
puts "==PERIPH NUM_MI=="
catch { puts "  [get_property CONFIG.NUM_MI [get_bd_cells ps7_axi_periph]]" } e