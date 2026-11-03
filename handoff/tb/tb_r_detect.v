// ============================================================
// r_detect 独立仿真：验证 blanking 屏蔽 T 波
// ============================================================
`timescale 1ns/1ps
module tb_r_detect;

    reg clk, rst_n, sig_valid, above;
    wire r_detect;

    r_detect #(.BLANK_LEN(50)) dut (
        .clk(clk), .rst_n(rst_n),
        .sig_valid(sig_valid), .above(above),
        .r_detect(r_detect)
    );

    initial clk = 0;
    always #10 clk = ~clk;      // 时钟频率无所谓，关键看采样节拍

    task tick;
        begin
            @(posedge clk); sig_valid = 1'b1;
            @(posedge clk); sig_valid = 1'b0;
        end
    endtask

    integer i;
    initial begin
        rst_n = 0; sig_valid = 0; above = 0;
        #50 rst_n = 1;

        // 场景1：R 波（应输出 r_detect）
        above = 1'b1; tick;
        above = 1'b0;

        // 场景2：紧跟的 T 波（10 tick 后，仍在 blanking，应被屏蔽）
        for (i = 0; i < 10; i = i + 1) tick;
        above = 1'b1; tick;
        above = 1'b0;

        // 场景3：blanking 结束后（再 40 tick），真 R 波再次检出
        for (i = 0; i < 40; i = i + 1) tick;
        above = 1'b1; tick;
        above = 1'b0;

        for (i = 0; i < 5; i = i + 1) tick;
        $display("SIM DONE at %0t ns", $time);
        $finish;
    end

endmodule