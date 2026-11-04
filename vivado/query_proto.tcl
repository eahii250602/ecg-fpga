open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
open_bd_design [get_files ecg_bd.bd]
puts "==DMA 所有含 protocol/width 的属性=="
foreach p [list_property [get_bd_cells axi_dma_0]] {
  if {[string match -nocase *protocol* $p] || [string match -nocase *data_width* $p]} {
    catch { puts "  $p = [get_property $p [get_bd_cells axi_dma_0]]" } e
  }
}
puts "==PC 宽度相关属性=="
foreach p [list_property [get_bd_cells axi_pc_0]] {
  if {[string match -nocase *width* $p] || [string match -nocase *protocol* $p]} {
    catch { puts "  $p = [get_property $p [get_bd_cells axi_pc_0]]" } e
  }
}