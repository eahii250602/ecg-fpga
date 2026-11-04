open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
open_bd_design [get_files ecg_bd.bd]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_protocol_converter:2.1 axi_pc_probe
foreach p [get_bd_pins -of_objects [get_bd_cells axi_pc_probe]] { puts "  PIN $p" }
delete_bd_objs [get_bd_cells axi_pc_probe]