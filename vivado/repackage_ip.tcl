open_project D:/ecg/vivado/ecg_system/ecg_system.xpr
set rc [catch {
    ipx::open_core -quiet D:/ecg/ip_repo/ecg_axi_1_0/component.xml core
    ipx::infer_bus_interfaces core
    ipx::save_core core
} err]
puts "### IPX RESULT: rc=$rc err=$err"