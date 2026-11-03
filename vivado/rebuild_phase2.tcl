# ============================================================
# 重建阶段 2：重新综合 + 实现 + 出比特流
#
#   前提：阶段 1 已完成（.gen 缓存已刷新，修复后的 HDL 已进入工程）
#   做法：复位 synth_1 / impl_1 → 一路跑到 write_bitstream
#
#   运行：
#     vivado.bat -mode batch -source rebuild_phase2.tcl -log rebuild_phase2.log
# ============================================================

puts "### PHASE2 START"

open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
puts "### project opened OK"

foreach r {synth_1 impl_1} {
    if { [catch { set run_obj [get_runs $r] } err] } {
        puts "### run $r NOT FOUND: $err"
    } else {
        puts "### resetting run $r ..."
        reset_run $r
    }
}

puts "### launching impl_1 -to_step write_bitstream  (预计 20-40 分钟) ..."
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1

puts "### STATUS   : [get_property STATUS [get_runs impl_1]]"
puts "### PROGRESS : [get_property PROGRESS [get_runs impl_1]]"

if { [get_property PROGRESS [get_runs impl_1]] ne "100%" } {
    puts "### !!! PHASE2 FAILED - 未跑到 100% !!!"
    puts "### 请把 rebuild_phase2.log 的最后 80 行发给助手"
    close_project
    exit 1
}

puts "### BITSTREAM DIR: [get_property DIRECTORY [get_runs impl_1]]"

close_project
puts "### PHASE2 EXIT OK"
exit 0
