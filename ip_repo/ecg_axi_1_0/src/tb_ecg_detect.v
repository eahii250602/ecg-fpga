// ============================================================
// 端到端集成：DDS → tick → 阈值 → R检测 → RR计数
// 验证：72次/分 rr_count≈208；180次/分 rr_count≈83
// ============================================================
`timescale 1ns/1ps
module tb_ecg_detect;

    // ============ 开关：仿真/上板 ============
    localparam SIM_MODE    = 1;                 // 1=慢时钟仿真
    localparam CLK_FREQ    = (SIM_MODE == 1) ? 1_250_000 : 100_000_000;
    localparam HALF_PERIOD = 1_000_000_000 / (2 * CLK_FREQ);
    localparam SAMPLE_FREQ = 250;
    localparam DIV         = CLK_FREQ / SAMPLE_FREQ;

    // FTW = f_out * 2^32 / CLK_FREQ
    localparam FTW_72  = (SIM_MODE == 1) ? 32'd4123  : 32'd52;
    localparam FTW_180 = (SIM_MODE == 1) ? 32'd10308 : 32'd129;

    // 阈值：60% * 2047 ≈ 1228，取 1200（必须 > T波峰值 614）
    localparam signed [11:0] THRESHOLD = 12'sd1200;

    reg                clk, rst_n;
    reg  [31:0]        ftw;
    wire signed [11:0] ecg_wave;
    wire [7:0]         addr_dbg;
    wire               sample_tick;
    wire               above;
    wire               r_detect;
    wire [15:0]        rr_count;
    wire               rr_valid;

    // ---- ① 信号源：DDS ----
    dds_ecg #(.AW(8)) u_dds (
        .clk(clk), .rst_n(rst_n), .ftw(ftw),
        .ecg_wave(ecg_wave), .addr_dbg(addr_dbg)
    );

    // ---- ② 采样节拍：250Hz ----
    tick_gen #(.DIV(DIV)) u_tick (
        .clk(clk), .rst_n(rst_n), .tick(sample_tick)
    );

    // ---- ③ 阈值比较（一行组合逻辑）----
    assign above = (ecg_wave > THRESHOLD);

    // ---- ④ R 波检测 ----
    r_detect #(.BLANK_LEN(50)) u_det (
        .clk(clk), .rst_n(rst_n),
        .sig_valid(sample_tick), .above(above),
        .r_detect(r_detect)
    );

    // ---- ⑤ RR 计数 ----
    rr_counter #(.CNT_W(16)) u_rr (
        .clk(clk), .rst_n(rst_n),
        .sig_valid(sample_tick), .r_detect(r_detect),
        .rr_count(rr_count), .rr_valid(rr_valid)
    );

    initial clk = 0;
    always #HALF_PERIOD clk = ~clk;

    initial begin
        rst_n = 0; ftw = 0;
        #1000 rst_n = 1;

        ftw = FTW_72;               // 72 次/分
        #2_500_000_000;             // 跑 2.5 秒（约 3 个心跳）

        ftw = FTW_180;              // 180 次/分
        #1_000_000_000;             // 跑 1 秒（约 3 个心跳）

        $display("SIM DONE at %0t", $time);
        $finish;
    end

endmodule