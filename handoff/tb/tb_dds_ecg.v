// ============================================================
// DDS 心电发生器仿真
// 验证：① 输出心电波形（非正弦）② 改 FTW 时心跳变快
// ============================================================
`timescale 1ns/1ps
module tb_dds_ecg;

    // ================================================================
    // ★★★ 唯一需要修改的参数：时钟频率 CLK_HZ（单位 Hz）★★★
    //   仿真（默认）：  1_250_000   = 1.25 MHz  内存小、跑得快，波形与上板等价
    //   上板/最终验证：100_000_000 = 100 MHz   （PS 的 FCLK_CLK0，PS+PL 系统用这个）    //   其余所有量都由它自动推导，不要手改。
    // ================================================================
    localparam integer CLK_HZ = 1_250_000;

    // ---------- 以下全部由 CLK_HZ 自动推导 ----------
    localparam integer CLK_PERIOD_NS = 1_000_000_000 / CLK_HZ;   // 时钟周期(ns)
    localparam integer HALF_CLK_NS   = CLK_PERIOD_NS / 2;        // 半周期(ns)
    localparam integer RESET_NS      = 4 * CLK_PERIOD_NS;        // 复位 4 个周期

    // FTW = 2^32 * f_out / CLK_HZ，其中 f_out = BPM / 60
    localparam [63:0] TWO32 = 64'd4294967296;                            // 2^32
    localparam integer FTW_60  = (TWO32 * 64'd1 + CLK_HZ/2) / CLK_HZ;    // 60 BPM
    localparam integer FTW_180 = (TWO32 * 64'd3 + CLK_HZ/2) / CLK_HZ;    // 180 BPM

    // 每搏时长只由 BPM 决定，与时钟频率无关
    localparam integer T_BEAT_60  = 1_000_000_000;   // 60 BPM -> 1 s
    localparam integer T_BEAT_180 = 340_000_000;     // 180 BPM -> 0.34 s

    reg                clk, rst_n;
    reg  [31:0]        ftw;
    wire signed [11:0] ecg_wave;
    wire [7:0]         addr_dbg;

    dds_ecg #(.AW(8)) dut (
        .clk(clk), .rst_n(rst_n), .ftw(ftw),
        .ecg_wave(ecg_wave), .addr_dbg(addr_dbg)
    );

    initial clk = 0;
    always #HALF_CLK_NS clk = ~clk;     // 周期 = 2*HALF_CLK_NS

    initial begin
        $dumpfile("dds_ecg.vcd");
        $dumpvars(0, tb_dds_ecg);
        rst_n = 0; ftw = 32'd0;
        #RESET_NS rst_n = 1;            // 复位覆盖若干个上升沿

        ftw = FTW_60;                   // 60 次/分
        #T_BEAT_60;

        ftw = FTW_180;                  // 180 次/分
        #T_BEAT_180;

        $display("CLK_HZ  = %0d Hz", CLK_HZ);
        $display("FTW_60  = %0d",     FTW_60);
        $display("FTW_180 = %0d",     FTW_180);
        $display("SIM DONE at %0t ns", $time);
        $finish;
    end

endmodule
