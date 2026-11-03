# set_clk62.tcl —— 把 ecg_axi 的 CLK_FREQ_HZ 改成 62.5 MHz
# 依据（2026-11-03 板上实测，三重交叉验证）：
#   ① Clocks.fclk0_mhz = 62.5
#   ② 20 秒检出 15 次 → 44.95 BPM → 每拍 1.335 s
#   ③ 每拍 206.5 个采样点 → 采样率 ≈154.7 Hz → fclk ≈ 61.9 MHz
# 目的：62.5e6/250 = 250000 → 采样率恢复 250Hz，PT 参数（按 250Hz 设计）才成立
# 注意：必须先 open_bd_design 才能 get_bd_cells（上一版漏了这步，报 BD 5-104）

open_project D:/ecg/vivado/ecg_system/ecg_system.xpr

open_bd_design [get_files ecg_bd.bd]

puts "### CLK_FREQ_HZ before: [get_property CONFIG.CLK_FREQ_HZ [get_bd_cells ecg_axi_0]]"
set_property CONFIG.CLK_FREQ_HZ {62500000} [get_bd_cells ecg_axi_0]
puts "### CLK_FREQ_HZ after : [get_property CONFIG.CLK_FREQ_HZ [get_bd_cells ecg_axi_0]]"

validate_bd_design
save_bd_design
close_bd_design [current_bd_design]

close_project
puts "### SET_CLK EXIT OK"
exit 0