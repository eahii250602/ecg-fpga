open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
puts "==REPO PATHS=="
catch { puts "  [get_property ip_repo_paths [current_project]]" } e
update_ip_catalog -rebuild
open_bd_design [get_files ecg_bd.bd]
puts "==ECG_AXI INTF AFTER CATALOG REBUILD=="
foreach i [get_bd_intf_pins -of_objects [get_bd_cells ecg_axi_0]] { puts "  $i" }
puts "==ECG_AXI PINS (m_axis?)=="
foreach p [get_bd_pins -of_objects [get_bd_cells ecg_axi_0]] {
  if {[string match *m_axis* $p] || [string match *drop* $p]} { puts "  $p" }
}