// tb_vitals.v —— vitals_hw 独立仿真
// 目的：不重建、不上板，直接在仿真里看 n / rej 是否按预期变化。
// 激励：每 207 个 sample_tick 产生一次 det_pulse，共 25 次（应累加 25-2-1=22 次）
`timescale 1ns/1ps

module tb_vitals;

    reg clk = 0;
    reg rst = 1;
    reg sample_tick = 0;
    reg det = 0;
    reg clear = 0;
    reg signed [11:0] xin = 12'sd100;
    reg signed [11:0] xout = 12'sd90;
    reg [15:0] rr = 16'd207;

    wire [1:0]  sqi;
    wire [31:0] ain, aout, sum_rr, sum_rr2, sum_d;
    wire [15:0] n, dbg_last, dbg_min, dbg_max, rej;
    wire        ready;

    vitals_hw u (
        .clk(clk), .rst(rst), .sample_tick(sample_tick),
        .x_in(xin), .x_out(xout),
        .det_pulse(det), .rr_samples(rr), .clear(clear),
        .sqi_level(sqi), .acc_in_q(ain), .acc_out_q(aout),
        .hrv_n(n), .hrv_sum_rr(sum_rr), .hrv_sum_rr2(sum_rr2),
        .hrv_sum_drr2(sum_d), .hrv_ready(ready),
        .dbg_last(dbg_last), .dbg_min(dbg_min), .dbg_max(dbg_max),
        .hrv_rej_cnt(rej)
    );

    always #8 clk = ~clk;      // 62.5 MHz

    integer i, k;
    initial begin
        $display("=== vitals_hw TB start ===");
        #200 rst = 0;
        #200;

        for (i = 0; i < 25; i = i + 1) begin
            // 间隔 207 个采样节拍
            for (k = 0; k < 207; k = k + 1) begin
                @(posedge clk); sample_tick <= 1'b1;
                @(posedge clk); sample_tick <= 1'b0;
                repeat (4) @(posedge clk);
            end
            // 一次检测脉冲
            @(posedge clk); det <= 1'b1;
            @(posedge clk); det <= 1'b0;
            repeat (20) @(posedge clk);
            $display("  beat %0d : n=%0d rej=%0d ref_ok=%0d", i, n, rej, (dbg_min != 16'hFFFF));
        end

        repeat (100) @(posedge clk);
        $display("=== RESULT ===");
        $display("  n        = %0d   (expect 22)", n);
        $display("  rej      = %0d   (expect 0)", rej);
        $display("  sum_rr   = %0d   (expect %0d)", sum_rr, 22*207);
        $display("  sum_rr2  = %0d   (expect %0d)", sum_rr2, 22*207*207);
        $display("  sum_drr2 = %0d   (expect 0)", sum_d);
        $display("  dbg min/max = %0d / %0d", dbg_min, dbg_max);
        $display("  ready    = %0d", ready);
        if (n == 22 && rej == 0 && sum_rr == 22*207) $display("  >>> PASS");
        else                                          $display("  >>> FAIL");
        $finish;
    end

endmodule
