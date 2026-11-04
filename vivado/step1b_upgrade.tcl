open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
update_ip_catalog -rebuild
open_bd_design [get_files ecg_bd.bd]
set rc [catch { upgrade_ip [get_bd_cells ecg_axi_0] } e]
puts "### UPGRADE rc=$rc : $e"
puts "==INTF=="
foreach i [get_bd_intf_pins -of_objects [get_bd_cells ecg_axi_0]] { puts "  $i" }
puts "==M_AXIS PINS=="
foreach p [get_bd_pins -of_objects [get_bd_cells ecg_axi_0]] {
  if {[string match *axis* $p] || [string match *drop* $p]} { puts "  $p" }
}