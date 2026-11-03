// ============================================================
// tb_rr_str.v —— 板上比特流参数形态的【1:1 复现】（2026-10-23）
// ------------------------------------------------------------
// ★ DUT 例化时 THRESHOLD 传字符串 "1200" —— 与 BD synth 包装层
//   .THRESHOLD("1200") 一字不差。目的：
//   ① 打印 DUT 实际例化出的 THRESHOLD 参数值（预期 48）
//   ② 看 rr_count 是否循环 {51, 51, 104}（= 板上实测值！）
//   ③ 顺带验证 Verilog 字符串→参数的截断语义
// ============================================================
`timescale 1ns/1ps
module tb_rr_str;

    localparam integer       CLK_FREQ_HZ = 1_250_000;
    localparam integer       SAMPLE_FREQ = 250;
    localparam [31:0]        FTW_72      = 32'd4123;

    reg clk = 0;
    always #400 clk = ~clk;              // 1.25 MHz

    reg rst_n = 0;

    reg  [4:0]  awaddr = 0, araddr = 0;
    reg  [2:0]  awprot = 0, arprot = 0;
    reg         awvalid = 0, wvalid = 0, arvalid = 0, bready = 0, rready = 0;
    reg  [31:0] wdata = 0;
    reg  [3:0]  wstrb = 4'hF;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [1:0]  bresp, rresp;
    wire [31:0] rdata;

    // ---- DUT：THRESHOLD 用【字符串 "1200"】例化（复现板上形态）----
    ecg_axi #(
        .CLK_FREQ_HZ        (CLK_FREQ_HZ),
        .SAMPLE_FREQ        (SAMPLE_FREQ),
        .THRESHOLD          ("1200"),     // ★★★ 字符串！★★★
        .BLANK_LEN          (50),
        .ROM_AW             (8),
        .C_S00_AXI_DATA_WIDTH(32),
        .C_S00_AXI_ADDR_WIDTH(5)
    ) dut (
        .s00_axi_aclk    (clk),
        .s00_axi_aresetn (rst_n),
        .s00_axi_awaddr  (awaddr),  .s00_axi_awprot(awprot),
        .s00_axi_awvalid (awvalid), .s00_axi_awready(awready),
        .s00_axi_wdata   (wdata),   .s00_axi_wstrb  (wstrb),
        .s00_axi_wvalid  (wvalid),  .s00_axi_wready (wready),
        .s00_axi_bresp   (bresp),   .s00_axi_bvalid (bvalid),
        .s00_axi_bready  (bready),
        .s00_axi_araddr  (araddr),  .s00_axi_arprot(arprot),
        .s00_axi_arvalid (arvalid), .s00_axi_arready(arready),
        .s00_axi_rdata   (rdata),   .s00_axi_rresp  (rresp),
        .s00_axi_rvalid  (rvalid),  .s00_axi_rready (rready)
    );

    // ---- AXI 写（两 valid 同拍握手）----
    task axi_write(input [4:0] a, input [31:0] d);
        integer t; reg done;
        begin
            @(posedge clk);
            awaddr <= a; awvalid <= 1'b1;
            wdata  <= d; wvalid  <= 1'b1; wstrb <= 4'hF; bready <= 1'b0;
            t = 0; done = 0;
            while (!done) begin
                @(posedge clk); t = t + 1;
                if (awvalid && awready && wvalid && wready) done = 1'b1;
                else if (t > 200) begin $display("*** TIMEOUT AW/W ***"); $finish; end
            end
            awvalid <= 1'b0; wvalid <= 1'b0;
            t = 0; done = 0;
            while (!done) begin
                @(posedge clk); t = t + 1;
                if (bvalid) done = 1'b1;
                else if (t > 200) begin $display("*** TIMEOUT BVALID ***"); $finish; end
            end
            bready <= 1'b1; @(posedge clk); bready <= 1'b0;
        end
    endtask

    // ---- 监视：TB 自数 tick ----
    integer tick_now = 0;
    always @(posedge clk)
        if (rst_n && dut.sample_tick) tick_now <= tick_now + 1;

    // ---- 监视：每个 r_detect + TB 自算间隔 ----
    integer last_det = -1;
    always @(posedge clk) begin
        if (rst_n && dut.r_detect) begin
            if (last_det < 0)
                $display("[%0t] DET #1  tick=%0d  wave=%0d", $time, tick_now, dut.ecg_wave);
            else
                $display("[%0t] DET      tick=%0d  TB间隔=%0d  wave=%0d",
                         $time, tick_now, tick_now - last_det, dut.ecg_wave);
            last_det <= tick_now;
        end
    end

    // ---- 监视：rr_count 锁存 ----
    always @(posedge clk)
        if (rst_n && dut.rr_valid)
            $display("[%0t]     ★ rr_count = %0d", $time, dut.rr_count_raw);

    // ---- 主流程 ----
    initial begin
        $display("======================================================");
        $display(" tb_rr_str : THRESHOLD 以【字符串 \"1200\"】例化（复现板上）");
        $display("======================================================");
        #1000 rst_n = 1'b1;
        repeat (5) @(posedge clk);

        $display("★ DUT 实际例化的 THRESHOLD = %0d (十进制) / %b (二进制)",
                 dut.THRESHOLD, dut.THRESHOLD);
        $display("★ 字符串 \"1200\" 的位模式 = 32'h%08h，截断到 12 位 = 0x%03h",
                 "1200", dut.THRESHOLD);

        axi_write(5'h00, FTW_72);
        $display("---- FTW=4123 (72BPM)，跑 4 秒（约 5 拍）----");
        repeat (40) #100_000_000;           // 4 s

        $display("======================================================");
        $display(" 预期: THRESHOLD 实际 = 48, rr_count 循环 {51,51,104}");
        $display(" 若与板上实测(51/104)一致 → 根因 100% 确认");
        $display("======================================================");
        $finish;
    end

    // ---- 看门狗 ----
    initial begin
        repeat (60) #100_000_000;
        $display("*** GLOBAL TIMEOUT ***");
        $finish;
    end

endmodule
