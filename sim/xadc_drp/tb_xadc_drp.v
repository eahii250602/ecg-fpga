`timescale 1ns/1ps
// ============================================================
// tb_xadc_drp.v —— XADC DRP 读时序自检测试台（D2 下午）
//
// 考法：
//   ① 逐通道读 DRP（den 打 1 拍）→ 检查 drdy 是否恰好在下一拍置位、
//      dout 是否等于该通道的"板上实测值"、[15:4] 码值是否正确
//   ② drdy 只允许保持 1 拍
//   ③ 背靠背读两次（den 连续两拍）→ 检查无丢拍/数据错位
// ============================================================
module tb_xadc_drp;

    reg clk = 1'b0;
    always #5 clk = ~clk;          // 100 MHz

    reg        den   = 1'b0;
    reg        dwe   = 1'b0;
    reg [6:0]  daddr = 7'd0;
    reg [15:0] di    = 16'd0;
    wire [15:0] dout;
    wire        drdy;

    xadc_drp_model dut (
        .dclk     (clk),
        .den_in   (den),
        .dwe_in   (dwe),
        .daddr_in (daddr),
        .di_in    (di),
        .do_out   (dout),
        .drdy_out (drdy)
    );

    integer pass = 0;
    integer fail = 0;

    // 读一个 DRP 寄存器并自检
    task drp_read(input [6:0] addr, input [15:0] exp, input [11:0] exp_code);
        begin
            @(negedge clk);
            daddr = addr;
            dwe   = 1'b0;
            den   = 1'b1;
            @(posedge clk);        // 模型在此采样 den
            @(negedge clk);
            den = 1'b0;

            // drdy 应恰好在 den 后的下一拍有效
            if (!drdy) begin
                fail = fail + 1;
                $display("FAIL addr=0x%02X: drdy 未在 den 后 1 拍置位", addr);
            end
            else if (dout !== exp) begin
                fail = fail + 1;
                $display("FAIL addr=0x%02X: dout=%04h 期望 %04h", addr, dout, exp);
            end
            else if (((dout >> 4) & 12'hFFF) !== exp_code) begin
                fail = fail + 1;
                $display("FAIL addr=0x%02X: code=%0d 期望 %0d",
                         addr, (dout >> 4) & 12'hFFF, exp_code);
            end
            else begin
                pass = pass + 1;
                $display("PASS addr=0x%02X dout=%04h code=%0d",
                         addr, dout, (dout >> 4) & 12'hFFF);
            end

            // drdy 只允许高 1 拍
            @(posedge clk);
            @(negedge clk);
            if (drdy) begin
                fail = fail + 1;
                $display("FAIL addr=0x%02X: drdy 保持超过 1 拍", addr);
            end
        end
    endtask

    initial begin
        $display("==== XADC DRP 时序测试台 ====");
        #20;

        drp_read(7'h00, 16'hA5F4, 12'd2655);   // 温度   53.52℃
        drp_read(7'h01, 16'h5792, 12'd1401);   // VCCINT 1.0261V
        drp_read(7'h02, 16'h9A99, 12'd2473);   // VCCAUX 1.8114V
        drp_read(7'h03, 16'h1650, 12'd357);    // V_P/V_N（悬空）
        drp_read(7'h10, 16'h15C2, 12'd348);    // VAUX0（未接线）

        // ---- 背靠背读：den 连续两拍，检查不丢拍 ----
        @(negedge clk);
        daddr = 7'h01; dwe = 1'b0; den = 1'b1;
        @(posedge clk);
        @(negedge clk);
        daddr = 7'h02; den = 1'b1;
        @(posedge clk);
        @(negedge clk);
        den = 1'b0;
        if (drdy && dout == 16'h9A99) begin
            pass = pass + 1;
            $display("PASS 背靠背读: 第二次读 dout=%04h", dout);
        end
        else begin
            fail = fail + 1;
            $display("FAIL 背靠背读: drdy=%b dout=%04h", drdy, dout);
        end

        repeat (5) @(posedge clk);
        $display("==== 结果: PASS=%0d FAIL=%0d ====", pass, fail);
        if (fail == 0)
            $display("RESULT: PASS");
        else
            $display("RESULT: FAIL");
        $finish;
    end

endmodule
