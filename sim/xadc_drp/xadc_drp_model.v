`timescale 1ns/1ps
// ============================================================
// xadc_drp_model.v —— XADC DRP 行为级模型（D2 下午仿真用）
//
// 用途：在仿真里复现 XADC 的 DRP 读时序，供 TB 验证；
//       结果寄存器预置为 2026-10-26 板上实测值，使仿真与板子一一对应。
//
// 寄存器内容（12 位码在 [15:4]，与 XADC 一致）：
//   DRP 0x00 温度   0xA5F4 → code 2655 → 53.52℃
//   DRP 0x01 VCCINT 0x5792 → code 1401 → 1.0261V
//   DRP 0x02 VCCAUX 0x9A99 → code 2473 → 1.8114V
//   DRP 0x03 V_P/VN 0x1650 → code 357  → 0.0876V（J5 悬空）
//   DRP 0x10 VAUX0  0x15C2 → code 348  → 0.0849V（未接线）
//
// DRP 时序（本模型约定）：
//   den 在 posedge 采样 → 下一拍 drdy=1、dout 有效（各保持 1 拍）
// ============================================================
module xadc_drp_model(
    input  wire        dclk,
    input  wire        den_in,
    input  wire        dwe_in,
    input  wire [6:0]  daddr_in,
    input  wire [15:0] di_in,
    output reg  [15:0] do_out,
    output reg         drdy_out
);

    reg [15:0] res [0:127];
    integer    i;

    initial begin
        for (i = 0; i < 128; i = i + 1)
            res[i] = 16'h0000;
        res[ 0] = 16'hA5F4;      // 温度
        res[ 1] = 16'h5792;      // VCCINT
        res[ 2] = 16'h9A99;      // VCCAUX
        res[ 3] = 16'h1650;      // V_P/V_N
        res[16] = 16'h15C2;      // VAUX0
    end

    always @(posedge dclk) begin
        drdy_out <= den_in;
        if (den_in)
            do_out <= dwe_in ? 16'h0000 : res[daddr_in];
    end

endmodule
