// ============================================================
// tb_rr_check.v —— rr_count 数值判别实验（2026-10-23）
// ------------------------------------------------------------
// 背景：板上 rr_count = 51/104，理论 206.5，静态分析全部正确。
//       本测试台把 ecg_axi【整个顶层】原样例化（含 AXI 从机 + 阈值比较
//       + 5 级链），FTW 用真实 AXI 写入，自动打印结果。
//
// 判读（预注册结论，防止事后圆场）：
//   A) rr_count ≈ 208(72BPM) / 83(180BPM)
//        → RTL 正确 → 板上比特流与源码不一致（重建比特流再上板）
//   B) rr_count ≈ 51 或乱值
//        → RTL 有 bug → 对照"TB 自测间隔"进一步定位：
//          TB 间隔对 + rr_count 错  → rr_counter 的 bug
//          TB 间隔也错             → 检测器/阈值比较的 bug
//
// 仿真参数（慢时钟模式，数学上与上板等价）：
//   CLK = 1.25 MHz → TICK_DIV = 5000 → 采样 250 Hz
//   FTW = 4123  → 72 BPM  → 理论 rr_count = 2^32/(4123×5000) = 208.4
//   FTW = 10308 → 180 BPM → 理论 rr_count = 2^32/(10308×5000) = 83.3
//   （时钟无关性：rr_count = 2^32/(FTW×TICK_DIV)，与 clk 频率无关）
// ============================================================
`timescale 1ns/1ps
module tb_rr_check;

    // ---- 参数（与 ecg_axi.v 上板值一致，仅时钟换成仿真慢钟）----
    localparam integer       CLK_FREQ_HZ = 1_250_000;
    localparam integer       SAMPLE_FREQ = 250;
    localparam signed [11:0] THRESHOLD   = 12'sd1200;
    localparam integer       BLANK_LEN   = 50;
    localparam integer       ROM_AW      = 8;
    localparam [31:0]        FTW_72      = 32'd4123;
    localparam [31:0]        FTW_180     = 32'd10308;

    // ---- 时钟：1.25 MHz（半周期 400 ns）----
    reg clk = 0;
    always #400 clk = ~clk;

    reg rst_n = 0;

    // ---- AXI4-Lite 主设备信号 ----
    reg  [4:0]  awaddr = 0, araddr = 0;
    reg  [2:0]  awprot = 0, arprot = 0;
    reg         awvalid = 0, wvalid = 0, arvalid = 0, bready = 0, rready = 0;
    reg  [31:0] wdata = 0;
    reg  [3:0]  wstrb = 4'hF;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [1:0]  bresp, rresp;
    wire [31:0] rdata;

    // ---- DUT：整个 ecg_axi 顶层 ----
    ecg_axi #(
        .CLK_FREQ_HZ        (CLK_FREQ_HZ),
        .SAMPLE_FREQ        (SAMPLE_FREQ),
        .THRESHOLD          (THRESHOLD),
        .BLANK_LEN          (BLANK_LEN),
        .ROM_AW             (ROM_AW),
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

    // ---- AXI 写（两 valid 同拍握手，与修复版从机匹配；带超时）----
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
                else if (t > 200) begin
                    $display("*** TIMEOUT #1: AW/W handshake ***"); $finish;
                end
            end
            awvalid <= 1'b0; wvalid <= 1'b0;
            t = 0; done = 0;
            while (!done) begin
                @(posedge clk); t = t + 1;
                if (bvalid) done = 1'b1;
                else if (t > 200) begin
                    $display("*** TIMEOUT #2: BVALID ***"); $finish;
                end
            end
            bready <= 1'b1; @(posedge clk); bready <= 1'b0;
        end
    endtask

    // ---- AXI 读（带超时）----
    task axi_read(input [4:0] a);
        integer t; reg done;
        begin
            @(posedge clk);
            araddr <= a; arvalid <= 1'b1; rready <= 1'b0;
            t = 0; done = 0;
            while (!done) begin
                @(posedge clk); t = t + 1;
                if (arvalid && arready) done = 1'b1;
                else if (t > 200) begin
                    $display("*** TIMEOUT #3: AR ***"); $finish;
                end
            end
            arvalid <= 1'b0;
            t = 0; done = 0;
            while (!done) begin
                @(posedge clk); t = t + 1;
                if (rvalid) done = 1'b1;
                else if (t > 200) begin
                    $display("*** TIMEOUT #4: RVALID ***"); $finish;
                end
            end
            rready <= 1'b1; @(posedge clk); rready <= 1'b0;
        end
    endtask

    // ---- 监视①：TB 自己数采样 tick（独立真值基准）----
    integer tick_now = 0;
    always @(posedge clk)
        if (rst_n && dut.sample_tick) tick_now <= tick_now + 1;

    // ---- 监视②：每个 r_detect 打印 + TB 自算检测间隔 ----
    integer last_det = -1;
    integer n_det    = 0;
    always @(posedge clk) begin
        if (rst_n && dut.r_detect) begin
            n_det <= n_det + 1;
            if (last_det < 0)
                $display("[%0t ns] DET #1  tick=%0d  wave=%0d",
                         $time, tick_now, dut.ecg_wave);
            else
                $display("[%0t ns] DET      tick=%0d  TB测得间隔=%0d  wave=%0d",
                         $time, tick_now, tick_now - last_det, dut.ecg_wave);
            last_det <= tick_now;
        end
    end

    // ---- 监视③：每次 rr_count 锁存打印（DUT 硬件实际输出）----
    always @(posedge clk)
        if (rst_n && dut.rr_valid)
            $display("[%0t ns]     ★ rr_count 锁存 = %0d", $time, dut.rr_count_raw);

    // ---- 主流程 ----
    initial begin
        $display("======================================================");
        $display(" tb_rr_check : rr_count 判别实验（ecg_axi 整链 + AXI）");
        $display(" 1.25MHz / 250Hz / FTW 4123(72BPM) -> 10308(180BPM)");
        $display(" 理论: 72BPM → rr_count ~ 208 ; 180BPM → ~ 83");
        $display("======================================================");
        #1000 rst_n = 1'b1;
        repeat (5) @(posedge clk);

        axi_write(5'h00, FTW_72);
        $display("---- FTW=4123 已写入，跑 5 秒（约 6 拍）----");
        repeat (50) #100_000_000;           // 50 × 100ms = 5s（拆开避免 32 位溢出）

        axi_write(5'h00, FTW_180);
        $display("---- 切换 FTW=10308 (180BPM)，跑 2.5 秒（约 7 拍）----");
        repeat (25) #100_000_000;           // 25 × 100ms = 2.5s

        axi_read(5'h08);                    // 正式走 AXI 读 0x08
        #100;
        $display("======================================================");
        $display(" 总检测数 = %0d", n_det);
        $display(" 最终 AXI 读 0x08 (rr_count) = %0d", rdata);
        $display(" 判读: 序列 ~208/83 → RTL 对，问题在板/比特流；");
        $display("       ~51 或乱值  → RTL 有 bug（间隔对→rr_counter 错，");
        $display("                     间隔错→检测器/阈值错）");
        $display("======================================================");
        $finish;
    end

    // ---- 全局看门狗 ----
    initial begin
        repeat (90) #100_000_000;           // 90 × 100ms = 9s（拆开避免 32 位溢出）
        $display("*** GLOBAL TIMEOUT : simulation stuck ***");
        $finish;
    end

endmodule
