`timescale 1ns/1ps
// ============================================================
// tb_ecg_axi_pt.v —— ecg_axi 整链测试台（H2 集成验证）
//
// 验证内容：
//   T1 读 VERSION  0x14 → 期望 0xEC600002（确认新设计）
//   T2 写 FTW=4123（1.25MHz 时钟下 = 72BPM，RR≈208）
//   T3 等 700 个采样 tick（约 2.8 秒仿真时间，3 拍以上）
//   T4 读 0x18（PT 的 RR）→ 期望 204~212
//   T5 读 0x08（旧检测器 RR）→ 期望 204~212（两者应一致）
//   T6 读 0x1C（PT 检测数）→ 期望 ≥ 2
// ============================================================
module tb_ecg_axi_pt;

    localparam integer DATA_W = 32;
    localparam integer ADDR_W = 5;
    localparam integer TMO    = 5000;

    reg clk = 1'b0;
    always #400 clk = ~clk;               // 1.25 MHz（TICK_DIV=5000 → 250Hz）
    reg rst_n = 1'b0;

    // ---- AXI 信号 ----
    reg  [ADDR_W-1:0] awaddr  = 0;
    reg  [2:0]        awprot  = 0;
    reg               awvalid = 0;
    wire              awready;

    reg  [DATA_W-1:0] wdata   = 0;
    reg  [3:0]        wstrb   = 4'hF;
    reg               wvalid  = 0;
    wire              wready;

    wire [1:0]        bresp;
    wire              bvalid;
    reg               bready  = 0;

    reg  [ADDR_W-1:0] araddr  = 0;
    reg  [2:0]        arprot  = 0;
    reg               arvalid = 0;
    wire              arready;

    wire [DATA_W-1:0] rdata;
    wire [1:0]        rresp;
    wire              rvalid;
    reg               rready  = 0;

    ecg_axi #(
        .CLK_FREQ_HZ (1_250_000),
        .SAMPLE_FREQ (250),
        .THRESHOLD   (1200),
        .BLANK_LEN   (50),
        .ROM_AW      (8)
    ) dut (
        .s00_axi_aclk    (clk),
        .s00_axi_aresetn (rst_n),
        .s00_axi_awaddr  (awaddr),
        .s00_axi_awprot  (awprot),
        .s00_axi_awvalid (awvalid),
        .s00_axi_awready (awready),
        .s00_axi_wdata   (wdata),
        .s00_axi_wstrb   (wstrb),
        .s00_axi_wvalid  (wvalid),
        .s00_axi_wready  (wready),
        .s00_axi_bresp   (bresp),
        .s00_axi_bvalid  (bvalid),
        .s00_axi_bready  (bready),
        .s00_axi_araddr  (araddr),
        .s00_axi_arprot  (arprot),
        .s00_axi_arvalid (arvalid),
        .s00_axi_arready (arready),
        .s00_axi_rdata   (rdata),
        .s00_axi_rresp   (rresp),
        .s00_axi_rvalid  (rvalid),
        .s00_axi_rready  (rready)
    );

    // ---------------- 写事务（带超时）----------------
    task axi_write(input [ADDR_W-1:0] addr, input [DATA_W-1:0] data);
        integer t;
        reg done;
        begin
            @(posedge clk);
            awaddr  <= addr;   awvalid <= 1'b1;
            wdata   <= data;   wvalid  <= 1'b1;   wstrb <= 4'hF;
            bready  <= 1'b0;

            t = 0; done = 0;
            while (!done) begin
                @(posedge clk);
                t = t + 1;
                if (awvalid && awready && wvalid && wready) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #1 : AW/W handshake, addr=0x%02X ***", addr);
                    $finish;
                end
            end
            awvalid <= 1'b0;
            wvalid  <= 1'b0;

            t = 0; done = 0;
            while (!done) begin
                @(posedge clk);
                t = t + 1;
                if (bvalid) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #2 : BVALID never came, addr=0x%02X ***", addr);
                    $finish;
                end
            end
            bready <= 1'b1;
            @(posedge clk);
            bready <= 1'b0;
            $display("  WRITE 0x%02X = 0x%08X   BRESP=%b  OK", addr, data, bresp);
        end
    endtask

    // ---------------- 读事务（精确比对，带超时）----------------
    task axi_read(input [ADDR_W-1:0] addr, input [DATA_W-1:0] expect, input [127:0] name);
        integer t;
        reg done;
        begin
            @(posedge clk);
            araddr  <= addr;   arvalid <= 1'b1;
            rready  <= 1'b0;

            t = 0; done = 0;
            while (!done) begin
                @(posedge clk);
                t = t + 1;
                if (arvalid && arready) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #3 : AR handshake, addr=0x%02X ***", addr);
                    $finish;
                end
            end
            arvalid <= 1'b0;

            t = 0; done = 0;
            while (!done) begin
                @(posedge clk);
                t = t + 1;
                if (rvalid) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #4 : RVALID never came, addr=0x%02X ***", addr);
                    $finish;
                end
            end
            rready <= 1'b1;
            if (rdata === expect)
                $display("  READ  0x%02X = 0x%08X   %s : PASS", addr, rdata, name);
            else
                $display("  READ  0x%02X = 0x%08X   %s : *** FAIL (expect 0x%08X) ***",
                         addr, rdata, name, expect);
            @(posedge clk);
            rready <= 1'b0;
        end
    endtask

    // ---------------- 读事务（范围比对）----------------
    task axi_read_range(input [ADDR_W-1:0] addr, input [DATA_W-1:0] lo, input [DATA_W-1:0] hi,
                        input [127:0] name);
        integer t;
        reg done;
        begin
            @(posedge clk);
            araddr  <= addr;   arvalid <= 1'b1;
            rready  <= 1'b0;

            t = 0; done = 0;
            while (!done) begin
                @(posedge clk);
                t = t + 1;
                if (arvalid && arready) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #5 : AR handshake, addr=0x%02X ***", addr);
                    $finish;
                end
            end
            arvalid <= 1'b0;

            t = 0; done = 0;
            while (!done) begin
                @(posedge clk);
                t = t + 1;
                if (rvalid) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #6 : RVALID never came, addr=0x%02X ***", addr);
                    $finish;
                end
            end
            rready <= 1'b1;
            if (rdata >= lo && rdata <= hi)
                $display("  READ  0x%02X = %0d   %s : PASS (范围 %0d..%0d)",
                         addr, rdata, name, lo, hi);
            else
                $display("  READ  0x%02X = %0d   %s : *** FAIL (期望 %0d..%0d) ***",
                         addr, rdata, name, lo, hi);
            @(posedge clk);
            rready <= 1'b0;
        end
    endtask

    // ---------------- 全局看门狗 ----------------
    initial begin
        repeat (2) #1_600_000_000;            // 3.2 秒仿真时间（单个常量不能超过 2^31-1）
        $display("*** GLOBAL TIMEOUT : simulation stuck ***");
        $finish;
    end

    // ---------------- 主流程 ----------------
    initial begin
        $display("==================================================");
        $display(" ecg_axi integration test  (XADC-free, PT chain)");
        $display("==================================================");

        rst_n = 0;
        repeat (20) @(posedge clk);
        rst_n = 1;
        repeat (10) @(posedge clk);

        $display("[T1] 读 VERSION 0x14，期望 0xEC600002（确认新设计）");
        axi_read(5'h14, 32'hEC600002, "version");

        $display("[T2] 写 FTW=4123（72BPM @1.25MHz，RR≈208）");
        axi_write(5'h00, 32'd4123);

        $display("[T3] 等 700 个采样 tick（≈2.8s 仿真时间，约 3 拍）...");
        repeat (700) begin
            repeat (5000) @(posedge clk);
        end

        $display("[T4] 读 0x18（PT 的 RR），期望 204..212");
        axi_read_range(5'h18, 32'd204, 32'd212, "pt_rr");

        $display("[T5] 读 0x08（旧检测器 RR），期望 204..212（两者应一致）");
        axi_read_range(5'h08, 32'd204, 32'd212, "old_rr");

        $display("[T6] 读 0x1C（PT 累计检测数），期望 ≥2");
        axi_read_range(5'h1C, 32'd2, 32'd100, "pt_det_cnt");

        $display("==================================================");
        $display(" ALL TESTS DONE");
        $display("==================================================");
        $finish;
    end

endmodule
