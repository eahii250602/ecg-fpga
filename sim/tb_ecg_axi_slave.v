// ============================================================
// ecg_axi_slave 的 AXI4-Lite 协议级测试台
// ============================================================
// 目的：定位"板上写操作疑似挂死"的问题
//   ★ 每个事务都带【超时检测】——
//     如果 BVALID / RVALID 一直不来，会明确报 *** TIMEOUT ***，
//     而不是让仿真无限跑下去（这正是板上"整机冻死"在仿真里的等价现象）
//
// 测试内容：
//   T1 复位
//   T2 读 0x14  -> 期望 0xEC600001（硬编码常量，验证读通道）
//   T3 写 0x00 = 0x34(52)  -> 期望 BVALID 到来（★ 关键：验证写通道）
//   T4 读 0x00  -> 期望 0x00000034（验证写入真的生效）
//   T5 写 0x04 = 123, 读 0x04 -> 验证第二个寄存器
//   T6 读 0x08  -> 期望模拟的 rr_count
//   T7 读 0x0C  -> 期望模拟的波形数据（含符号扩展检查）
//
// 用法（Vivado）：
//   1. 新建 RTL 工程
//   2. Add Sources      : ecg_axi_slave_lite_v1_0_S00_AXI.v
//   3. Add Sim Sources  : 本文件
//   4. Run Behavioral Simulation
//   5. 看 Tcl Console 的文字输出
// ============================================================
`timescale 1 ns / 1 ps

module tb_ecg_axi_slave;

    localparam integer DATA_W = 32;
    localparam integer ADDR_W = 5;
    localparam integer TMO    = 200;    // 单次事务超时（时钟周期）

    reg clk = 0;
    reg rst_n = 0;
    always #5 clk = ~clk;               // 100 MHz

    // ---------------- AXI 信号 ----------------
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

    // ---------------- 模拟用户侧输入 ----------------
    wire [DATA_W-1:0] rr_count_in  = 32'h0000_00D0;   // 模拟 rr_count = 208
    wire [DATA_W-1:0] wave_data_in = 32'hFFFF_FF9C;   // 模拟波形值   = -100
    wire [DATA_W-1:0] ftw_out;
    wire [DATA_W-1:0] wave_addr_out;

    // ---------------- DUT ----------------
    ecg_axi_slave_lite_v1_0_S00_AXI #(
        .C_S_AXI_DATA_WIDTH(DATA_W),
        .C_S_AXI_ADDR_WIDTH(ADDR_W)
    ) dut (
        .reg_ftw       (ftw_out),
        .reg_rr_count  (rr_count_in),
        .reg_wave_addr (wave_addr_out),
        .reg_wave_data (wave_data_in),

        .S_AXI_ACLK    (clk),
        .S_AXI_ARESETN (rst_n),

        .S_AXI_AWADDR  (awaddr),
        .S_AXI_AWPROT  (awprot),
        .S_AXI_AWVALID (awvalid),
        .S_AXI_AWREADY (awready),

        .S_AXI_WDATA   (wdata),
        .S_AXI_WSTRB   (wstrb),
        .S_AXI_WVALID  (wvalid),
        .S_AXI_WREADY  (wready),

        .S_AXI_BRESP   (bresp),
        .S_AXI_BVALID  (bvalid),
        .S_AXI_BREADY  (bready),

        .S_AXI_ARADDR  (araddr),
        .S_AXI_ARPROT  (arprot),
        .S_AXI_ARVALID (arvalid),
        .S_AXI_ARREADY (arready),

        .S_AXI_RDATA   (rdata),
        .S_AXI_RRESP   (rresp),
        .S_AXI_RVALID  (rvalid),
        .S_AXI_RREADY  (rready)
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

            // ---- 等 AW 与 W 同时被接受 ----
            t = 0; done = 0;
            while (!done) begin
                @(posedge clk);
                t = t + 1;
                if (awvalid && awready && wvalid && wready) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #1 : AW/W handshake, addr=0x%02X (awready=%b wready=%b) ***",
                             addr, awready, wready);
                    $finish;
                end
            end
            awvalid <= 1'b0;
            wvalid  <= 1'b0;

            // ---- 等写响应 BVALID ----
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

    // ---------------- 读事务（带超时）----------------
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

    // ---------------- 写事务：AW 先到、W 后到（合规主设备行为）----------------
    // ★ 修复版从机只在两 valid 同拍时握手，所以主设备必须【保持 AWVALID】
    //   直到 WVALID 出现、两通道同拍握手为止 —— 这正是 AXI 规范对主设备的要求。
    task axi_write_awfirst(input [ADDR_W-1:0] addr, input [DATA_W-1:0] data);
        integer t;
        reg done;
        begin
            @(posedge clk);
            awaddr  <= addr;   awvalid <= 1'b1;      // 只先发 AW，并保持
            wvalid  <= 1'b0;   bready  <= 1'b0;
            repeat (2) @(posedge clk);                // AW 先悬 2 拍（期间 awready 应为 0）
            wdata  <= data;   wvalid <= 1'b1;   wstrb <= 4'hF;   // W 后到
            t = 0; done = 0;
            while (!done) begin                       // 等两通道同拍握手
                @(posedge clk);
                t = t + 1;
                if (awvalid && awready && wvalid && wready) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #A1 : AW/W handshake, addr=0x%02X (awready=%b wready=%b) ***",
                             addr, awready, wready);
                    $finish;
                end
            end
            awvalid <= 1'b0;
            wvalid  <= 1'b0;
            t = 0; done = 0;
            while (!done) begin                       // 等 BVALID
                @(posedge clk);
                t = t + 1;
                if (bvalid) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #A3 : BVALID (AW-first), addr=0x%02X ***", addr);
                    $finish;
                end
            end
            bready <= 1'b1;
            @(posedge clk);
            bready <= 1'b0;
            $display("  WRITE(AW-first) 0x%02X = 0x%08X  BRESP=%b  OK", addr, data, bresp);
        end
    endtask

    // ---------------- 写事务：W 先到、AW 后到（合规主设备行为）★★ ----------------
    // AXI 规范允许 W 通道先于 AW 到达；主设备必须保持 WVALID 直到握手。
    // 旧从机在这种顺序下死锁（BVALID 永不来 → 板上整机冻死，T10 已复现）；
    // 修复后的从机必须能正确完成事务 —— 本任务验证修复生效。
    task axi_write_wfirst(input [ADDR_W-1:0] addr, input [DATA_W-1:0] data);
        integer t;
        reg done;
        begin
            @(posedge clk);
            wdata   <= data;   wvalid <= 1'b1;  wstrb <= 4'hF;   // 只先发 W，并保持
            awvalid <= 1'b0;   bready  <= 1'b0;
            repeat (2) @(posedge clk);                // W 先悬 2 拍（期间 wready 应为 0）
            awaddr <= addr;   awvalid <= 1'b1;        // AW 后到
            t = 0; done = 0;
            while (!done) begin                       // 等两通道同拍握手
                @(posedge clk);
                t = t + 1;
                if (awvalid && awready && wvalid && wready) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #W1 : AW/W handshake (W-first), addr=0x%02X (awready=%b wready=%b) ***",
                             addr, awready, wready);
                    $finish;
                end
            end
            awvalid <= 1'b0;
            wvalid  <= 1'b0;
            t = 0; done = 0;          // ★ 等 BVALID —— 旧代码在这里死锁，修复后必须正常返回
            while (!done) begin
                @(posedge clk);
                t = t + 1;
                if (bvalid) done = 1;
                else if (t > TMO) begin
                    $display("  *** TIMEOUT #W3 : BVALID never came (W-first), addr=0x%02X ***", addr);
                    $display("  *** -> SLAVE WRITE FSM DEADLOCK on W-before-AW ordering ***");
                    $finish;
                end
            end
            bready <= 1'b1;
            @(posedge clk);
            bready <= 1'b0;
            $display("  WRITE(W-first) 0x%02X = 0x%08X  BRESP=%b  OK", addr, data, bresp);
        end
    endtask

    // ---------------- 全局看门狗 ----------------
    initial begin
        #500000;                                   // 500 us 总超时
        $display("*** GLOBAL TIMEOUT : simulation stuck ***");
        $finish;
    end

    // ---------------- 主测试流程 ----------------
    initial begin
        $dumpfile("tb_ecg_axi_slave.vcd");
        $dumpvars(0, tb_ecg_axi_slave);

        $display("==================================================");
        $display(" AXI4-Lite slave testbench  (write/read protocol)");
        $display("==================================================");

        // ---- T1 复位 ----
        $display("[T1] reset ...");
        rst_n = 0;
        repeat (10) @(posedge clk);
        rst_n = 1;
        repeat (5) @(posedge clk);
        $display("     done. awready=%b wready=%b", awready, wready);

        // ---- T2 读版本号（寄存器5，字节地址 0x14）----
        $display("[T2] read version @0x14");
        axi_read(5'h14, 32'hEC600001, "version");

        // ---- T3 ★ 写 FTW（寄存器0，字节地址 0x00）----
        $display("[T3] WRITE 0x00 = 52  (this is the key test)");
        axi_write(5'h00, 32'd52);
        $display("     reg_ftw output = %d", ftw_out);

        // ---- T4 读回 FTW ----
        $display("[T4] read back 0x00");
        axi_read(5'h00, 32'd52, "ftw readback");

        // ---- T5 写/读波形地址寄存器（寄存器1，字节地址 0x04）----
        $display("[T5] write 0x04 = 123, then read back");
        axi_write(5'h04, 32'd123);
        axi_read(5'h04, 32'd123, "wave_addr");
        $display("     reg_wave_addr output = %d", wave_addr_out);

        // ---- T6 读 rr_count（寄存器2，字节地址 0x08）----
        $display("[T6] read 0x08 (rr_count, expect 208)");
        axi_read(5'h08, 32'h000000D0, "rr_count");

        // ---- T7 读波形数据（寄存器3，字节地址 0x0C）----
        $display("[T7] read 0x0C (wave_data, expect -100)");
        axi_read(5'h0C, 32'hFFFFFF9C, "wave_data");

        // ---- T8 越界地址读（0x18）----
        $display("[T8] read 0x18 (out of range -> expect 0)");
        axi_read(5'h18, 32'h00000000, "out-of-range");

        // ---- T9  AW 先到、W 后到（合法顺序之一）----
        $display("[T9] WRITE with AW-before-W ordering");
        axi_write_awfirst(5'h04, 32'h000000AB);
        axi_read(5'h04, 32'h000000AB, "awfirst readback");

        // ---- T10 ★★ W 先到、AW 后到（旧代码在此死锁；修复后必须通过）----
        $display("[T10] WRITE with W-before-AW ordering (old code deadlocked here)");
        axi_write_wfirst(5'h00, 32'h000000CD);
        axi_read(5'h00, 32'h000000CD, "wfirst correct reg");
        axi_read(5'h04, 32'h000000AB, "T9 value intact");

        $display("==================================================");
        $display(" ALL TESTS DONE (no timeout)  --> write channel OK");
        $display("==================================================");
        $finish;
    end

endmodule
