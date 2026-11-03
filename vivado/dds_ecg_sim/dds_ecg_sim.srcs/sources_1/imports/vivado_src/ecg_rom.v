// ============================================================
// 心电波形查找表：256 x 12bit
// 数据来自 Python 生成的 ecg_256x12.mem（偏移二进制，2048 = 基线）
// 输出转换 有符号：wave = mem_data - 2048
// ============================================================
module ecg_rom #(
    parameter MEM_FILE = "ecg_256x12.mem",
    parameter DEPTH    = 256,
    parameter AW       = 8
)(
    input  wire                clk,
    input  wire [AW-1:0]       addr,
    output reg  signed [11:0]  wave
);

    reg [11:0] mem [0:DEPTH-1];

    initial begin
           $readmemh("D:/ecg/vivado_src/ecg_256x12.mem", mem);
    end

    always @(posedge clk) begin
        wave <= $signed({1'b0, mem[addr]}) - 12'sd2048;   // 偏移码 -> 有符号
    end

endmodule