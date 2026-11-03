// ============================================================
// 基于 DDS 的心电波形发生器（RTL 与时钟频率无关，心率由 FTW 决定）
//   f_out = FTW * f_clk / 2^32    心率(BPM) = f_out * 60
//   => FTW = 2^32 * (BPM/60) / f_clk
//
// 不同 f_clk 下的 FTW（BPM -> FTW）：
//   f_clk = 100 MHz（上板，PS 的 FCLK_CLK0）：60 -> 43，120 -> 86，180 -> 129
//   f_clk = 1.25 MHz（仿真）：60 -> 3436，120 -> 6872，180 -> 10308
// ============================================================
module dds_ecg #(
    parameter PHASE_W  = 32,
    parameter AW       = 8,                 // 表地址位宽：2^8 = 256 点
    parameter MEM_FILE = "D:/ecg/vivado_src/ecg_256x12.mem"
)(
    input  wire                clk,
    input  wire                rst_n,
    input  wire [PHASE_W-1:0]  ftw,
    output wire signed [11:0]  ecg_wave,
    output wire [AW-1:0]       addr_dbg
);

    reg [PHASE_W-1:0] phase;

    // 相位累加器（DDS 核心）
    always @(posedge clk) begin
        if (!rst_n) phase <= {PHASE_W{1'b0}};
        else        phase <= phase + ftw;
    end

    // 相位截断：取高 AW 位作为查找表地址
    wire [AW-1:0] addr = phase[PHASE_W-1 -: AW];
    assign addr_dbg = addr;

    // 查表得到心电幅值
    ecg_rom #(.MEM_FILE(MEM_FILE), .DEPTH(1<<AW), .AW(AW)) u_rom (
        .clk  (clk),
        .addr (addr),
        .wave (ecg_wave)
    );

endmodule