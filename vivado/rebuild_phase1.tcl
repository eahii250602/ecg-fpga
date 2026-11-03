# ============================================================
# 重建阶段 1：清掉过期缓存，强制 Vivado 重新从 ip_repo 读入修复后的 IP HDL
#
#   背景：工程 .gen 缓存里的 ecg_axi_slave_lite_v1_0_S00_AXI.v 是【旧版】
#         （含 state_write 状态机，无 aw_en），直接出比特流会得到旧的坏逻辑。
#   做法：删掉 .gen → 重开工程 → 重新生成 BD/IP 输出产物
#         → Vivado 会从 D:/ecg/ip_repo/ecg_axi_1_0/hdl/ 重新拷贝修复后的 HDL
#
#   运行：
#     vivado.bat -mode batch -source rebuild_phase1.tcl -log rebuild_phase1.log
# ============================================================

set gen_dir "D:/ecg/vivado/ecg_system/ecg_system.gen"

puts "### PHASE1 START"
puts "### target cache dir = $gen_dir"

if { [file exists $gen_dir] } {
    puts "### deleting stale .gen ..."
    file delete -force $gen_dir
    puts "### .gen DELETED"
} else {
    puts "### .gen not present, nothing to delete"
}

puts "### opening project ..."
open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
puts "### project opened OK"

# ---- 重新生成 BD 的全部输出产物（会重新收集 IP 源文件到 .gen）----
if { [catch { set bd_list [get_files -all -filter {FILE_TYPE == "Block Designs"}] } err] } {
    puts "### ERROR getting BD list: $err"
    set bd_list {}
}
puts "### BD files found: $bd_list"

foreach bd $bd_list {
    puts "### generate_target all --> $bd"
    if { [catch { generate_target all $bd } err] } {
        puts "### WARNING generate_target(BD) failed: $err"
    } else {
        puts "### BD generate_target OK"
    }
}

# ---- 对本工程内的 ecg_axi IP 实例再显式刷新一次 ----
if { [catch { set ip_list [get_ips -all] } err ] } {
    puts "### WARNING get_ips failed: $err"
    set ip_list {}
}
puts "### IPs found: $ip_list"

foreach ip $ip_list {
    if { [string match "*ecg_axi*" $ip] } {
        puts "### refreshing IP: $ip"
        if { [catch { reset_target all $ip } e1] } { puts "###   reset_target warn: $e1" }
        if { [catch { generate_target all $ip } e2] } { puts "###   generate_target warn: $e2" }
        puts "###   IP refresh done"
    }
}

puts "### closing project ..."
close_project

puts "### PHASE1 EXIT OK"
exit 0
