`timescale 1ns/1ps
// ============================================================
// tb_pt_chain.v —— pt_chain 自检测试台（H2）
//
// 输入：pt_input.hex（4096 个 12 位补码样本，隔壁 pt_golden/out 生成）
// 输出：rtl_rpeaks.txt（检出的 R 峰采样序号，每行一个）
// 判据：与 golden_rpeaks.csv 用 compare_rpeaks.py 对账（±2、≥95%）
// ============================================================
module tb_pt_chain;

    localparam N = 4096;

    reg clk = 1'b0;
    always #5 clk = ~clk;          // 100 MHz
    reg rst_n = 1'b0;

    reg        s_valid = 1'b0;
    reg [11:0] s_data  = 12'd0;
    wire       r_detect;
    wire [15:0] r_index;

    pt_chain dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .s_valid  (s_valid),
        .s_data   (s_data),
        .r_detect (r_detect),
        .r_index  (r_index)
    );

    reg [11:0] stim [0:N-1];
    integer    fd;
    integer    hits = 0;
    integer    i;

    // ---- 记录检测 ----
    always @(posedge clk) begin
        if (r_detect) begin
            $fwrite(fd, "%0d\n", r_index);
            $display("R#%0d index=%0d", hits, r_index);
            hits = hits + 1;
        end
    end

    initial begin : STIM
        $readmemh("pt_input.hex", stim);
        fd = $fopen("rtl_rpeaks.txt", "w");
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;

        @(negedge clk);
        s_valid = 1'b1;
        s_data  = stim[0];
        for (i = 1; i < N; i = i + 1) begin
            @(posedge clk);
            @(negedge clk);
            s_data = stim[i];
        end
        // 补 120 个零样本：让流水排空、候选峰 50 拍倒计时跑完（否则最后一拍不提交）
        for (i = 0; i < 120; i = i + 1) begin
            @(posedge clk);
            @(negedge clk);
            s_data = 12'd0;
        end
        @(posedge clk);
        @(negedge clk);
        s_valid = 1'b0;
    end

    initial begin : DONE
        #3_000_000;                // 3ms 超时保护
        $fclose(fd);
        $display("==== 共检出 %0d 个 R 峰 ====", hits);
        $display("RESULT: DONE");
        $finish;
    end

endmodule
