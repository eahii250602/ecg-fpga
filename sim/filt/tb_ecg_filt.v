`timescale 1ns / 1ps
//=============================================================================
// tb_ecg_filt.v —— ecg_filt 的激励台（只用于仿真，不综合）
//
// 干的事：
//   1. 自己造时钟（62.5MHz，周期 16ns）
//   2. 从 filt_input.hex 读 2000 个样本，一个一个喂给 DUT
//   3. 每喂一个，等 dout_valid，把 dout 抄进 rtl_out.txt
//   4. 跑完打印采集数量
//
// 对齐约定（关键）：
//   · 所有激励在 negedge 驱动（避免和 posedge 抢，产生竞争）
//   · dout_valid 为高那一拍，dout 就是该样本的结果
//=============================================================================
module tb_ecg_filt;

    localparam integer N    = 2000;
    localparam real    TCLK = 16.0;          // 62.5MHz

    reg clk = 1'b0;
    always #(TCLK/2.0) clk = ~clk;

    reg               rst         = 1'b1;
    reg               sample_tick = 1'b0;
    reg  signed [11:0] din        = 12'sd0;
    wire signed [11:0] dout;
    wire               dout_valid;

    reg [11:0] mem [0:N-1];

    integer fd;
    integer i;
    integer guard;
    integer ncap;

    //--------------------------------------------------------------- 被测模块
    ecg_filt dut (
        .clk        (clk),
        .rst        (rst),
        .sample_tick(sample_tick),
        .din        (din),
        .dout       (dout),
        .dout_valid (dout_valid)
    );

    //--------------------------------------------------------------- 主流程
    initial begin
        $readmemh("D:/ecg/sim/filt/out/filt_input.hex", mem);
        fd = $fopen("D:/ecg/sim/filt/out/rtl_out.txt", "w");
        if (fd == 0) begin
            $display("ERROR: 打不开输出文件");
            $finish;
        end

        // 复位 5 拍
        rst = 1'b1;
        repeat (5) @(negedge clk);
        rst = 1'b0;
        repeat (3) @(negedge clk);

        ncap = 0;
        for (i = 0; i < N; i = i + 1) begin
            @(negedge clk);
            din         = mem[i];
            sample_tick = 1'b1;
            @(negedge clk);
            sample_tick = 1'b0;

            // 等这一拍的 dout_valid（正常情况下 2 拍后到）
            guard = 0;
            while (!dout_valid && guard < 200) begin
                @(negedge clk);
                guard = guard + 1;
            end

            if (!dout_valid) begin
                $display("ERROR: 第 %0d 个样本等 dout_valid 超时", i);
                $fclose(fd);
                $finish;
            end

            $fdisplay(fd, "%0d", dout);
            ncap = ncap + 1;
        end

        $fclose(fd);
        $display("DONE: 采集 %0d 个输出 -> rtl_out.txt", ncap);
        $finish;
    end

    //--------------------------------------------------------------- 超时保护
    initial begin
        #(TCLK * (N * 12 + 500));
        $display("ERROR: 全局超时（可能卡在某个等待里）");
        $finish;
    end

endmodule