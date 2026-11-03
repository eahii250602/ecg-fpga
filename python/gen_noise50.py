import math
lines = []
for k in range(256):
    v = int(round(1024.0 * math.sin(2.0 * math.pi * k / 256.0)))
    sign = "-" if v < 0 else ""
    lines.append("        sin_tab[%3d] = %s12'sd%d;" % (k, sign, abs(v)))
tab = "\n".join(lines)

src = '''`timescale 1ns / 1ps
//=============================================================================
// noise50.v —— 内部 50Hz 工频干扰注入器（D4/D5 测试专用）
//
// 为什么需要：板上没有外部信号源，DDS 波形是干净的，无法验证"50Hz 抑制"。
//   本模块在 DDS 输出上叠加一个【可开关、幅度可调】的 50Hz 正弦，
//   制造"心电图 + 工频干扰"的真实场景，再由 ecg_filt 滤掉，
//   从而在板上实测抑制比。
//
// 用法：filt_ctl(0x10) bit2 = 1 开启注入；[23:8] = 幅度（单位 LSB）
//       en = 0 时 dout 恒等于 din（旁路），行为与旧版完全一致
//
// 相位累加器：FTW = 50 * 2^32 / 62500000 = 3435.97 -> 3436
// 正弦表：256 点，幅度 1024（即 Q1.10），叠加时 (sin*amp)>>10 还原成 LSB
//=============================================================================
module noise50 (
    input  wire               clk,
    input  wire               rst,          // 同步复位，高有效
    input  wire               en,           // 1 = 注入
    input  wire [15:0]        amp,          // 幅度（0~2047 LSB）
    input  wire signed [11:0] din,          // DDS 输出
    output reg  signed [11:0] dout          // 叠加后（12 位饱和）
);

    localparam [31:0] FTW50 = 32'd3436;

    // ---- 相位累加器：每拍加 FTW50，2^32 对应一整圈 ----
    reg [31:0] ph;
    always @(posedge clk) begin
        if (rst) ph <= 32'd0;
        else     ph <= ph + FTW50;
    end

    wire [7:0] idx = ph[31:24];             // 高 8 位 = 表地址（0~255）

    // ---- 256 点正弦表，幅度 1024 ----
    reg signed [11:0] sin_tab [0:255];
    initial begin
__TABLE__
    end

    wire signed [11:0] sin_v = sin_tab[idx];
    wire signed [27:0] prod  = sin_v * $signed({1'b0, amp});   // 12 位 x 16 位
    wire signed [17:0] nval  = prod[27:10];                    // >>> 10 还原成 LSB
    wire signed [17:0] sum   = din + nval;

    always @(posedge clk) begin
        if (rst)
            dout <= 12'sd0;
        else if (!en)
            dout <= din;                    // 旁路
        else if (sum > 18'sd2047)
            dout <= 12'sd2047;              // 饱和
        else if (sum < -18'sd2048)
            dout <= -12'sd2048;
        else
            dout <= sum[11:0];
    end

endmodule
'''
src = src.replace("__TABLE__", tab)
open(r"D:\ecg\ip_repo\ecg_axi_1_0\hdl\noise50.v", "w", encoding="utf-8", newline="\n").write(src)
print("ok lines:", src.count("\n"))
