// ============================================================
// 采样节拍生成器：每 DIV 个时钟输出一个单周期高脉冲
//   仿真 SIM_MODE=1: CLK=1.25MHz -> DIV=5000  -> 250Hz
//   上板:           CLK=100MHz  -> DIV=400000 -> 250Hz
// 输出的 tick 直接接给 r_detect / rr_counter 的 sig_valid
// ============================================================
module tick_gen #(
    parameter DIV = 5000
)(
    input  wire clk,
    input  wire rst_n,
    output reg  tick
);
    localparam CNT_W = $clog2(DIV);   // 自动算位宽

    reg [CNT_W-1:0] cnt;

    always @(posedge clk) begin
        if (!rst_n) begin
            cnt  <= {CNT_W{1'b0}};
            tick <= 1'b0;
        end
        else if (cnt == DIV - 1) begin
            cnt  <= {CNT_W{1'b0}};
            tick <= 1'b1;             // 只高一个时钟周期
        end
        else begin
            cnt  <= cnt + 1'b1;
            tick <= 1'b0;
        end
    end
endmodule