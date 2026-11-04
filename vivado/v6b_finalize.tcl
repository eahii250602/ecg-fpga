open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
open_bd_design [get_files ecg_bd.bd]
set rc [catch { set_property CONFIG.ASSOCIATED_BUSIF {S00_AXI:M_AXIS} [get_bd_pins ecg_axi_0/s00_axi_aclk] } e]
puts "### ASSOC rc=$rc $e"
set rc [catch { validate_bd_design } ev]
puts "### VALIDATE rc=$rc"
if {$rc == 0} { save_bd_design; puts "### SAVED OK" }
puts "==FINAL ADDR MAP=="
foreach seg [get_bd_addr_segs -quiet] { set o [get_property -quiet OFFSET $seg]; if {$o ne ""} { puts "  $seg = $o" } }