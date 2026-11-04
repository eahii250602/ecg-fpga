open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
open_bd_design [get_files ecg_bd.bd]
puts "==CELLS=="
foreach c [get_bd_cells] { puts "  $c" }
puts "==ECG_AXI_INTF=="
foreach i [get_bd_intf_pins -of_objects [get_bd_cells ecg_axi_0]] { puts "  $i" }
puts "==PS7_INTF=="
foreach i [get_bd_intf_pins -of_objects [get_bd_cells processing_system7_0]] { puts "  $i" }
puts "==PERIPH=="
puts "  NUM_MI=[get_property CONFIG.NUM_MI [get_bd_cells ps7_axi_periph]]"