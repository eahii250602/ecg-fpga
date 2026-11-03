// ============================================================
// 心电波形查找表：256 x 12bit
// 数据来自 Python 生成的 ecg_256x12.mem（偏移二进制，2048 = 基线）
// 输出转换 有符号：wave = mem_data - 2048
// ============================================================
module ecg_rom #(
    // $readmemh 用绝对路径：Vivado 仿真/综合都能稳定找到文件
    // ⚠️ 可复现性待改进：最终版建议改用 Block Memory Generator IP + .coe
    //    把波形数据固化进 IP，彻底摆脱运行时文件路径依赖
    parameter MEM_FILE = "D:/ecg/vivado_src/ecg_256x12.mem",
    parameter DEPTH    = 256,
    parameter AW       = 8
)(
    input  wire                clk,
    input  wire [AW-1:0]       addr,
    output reg  signed [11:0]  wave
);

    reg [11:0] mem [0:DEPTH-1];

    initial begin
        $readmemh(MEM_FILE, mem);
    end

    always @(posedge clk) begin
        wave <= $signed({1'b0, mem[addr]}) - 12'sd2048;   // 偏移码 -> 有符号
    end

endmodule