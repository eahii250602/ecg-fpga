// ============================================================
// R 波检测状态机（250Hz 采样基准）
// 固定阈值 + 生理不响应期(blanking)
//   BLANK_LEN = 50 个采样点 = 200ms @ 250Hz
// 状态：IDLE（等待超阈值） / BLANK（不响应期，屏蔽 T 波）
// 输出 r_detect：与采样 tick 对齐的单周期脉冲
// ============================================================
module r_detect #(
    parameter BLANK_LEN = 50
)(
    input  wire clk,
    input  wire rst_n,
    input  wire sig_valid,            // 采样 tick（250Hz，来自 tick_gen）
    input  wire above,                // 当前采样点是否超阈值
    output wire r_detect              // 检出 R 波：单周期高脉冲
);
    localparam S_IDLE  = 1'b0;
    localparam S_BLANK = 1'b1;

    reg        state;
    reg [15:0] blank_cnt;

    assign r_detect = (state == S_IDLE) && sig_valid && above;

    always @(posedge clk) begin
        if (!rst_n) begin
            state     <= S_IDLE;
            blank_cnt <= 16'd0;
        end
        else if (sig_valid) begin
            if (state == S_IDLE) begin
                if (above) begin
                    state     <= S_BLANK;
                    blank_cnt <= 16'd0;
                end
            end
            else begin
                if (blank_cnt == BLANK_LEN - 1)
                    state <= S_IDLE;
                else
                    blank_cnt <= blank_cnt + 1'b1;
            end
        end
    end

endmodule