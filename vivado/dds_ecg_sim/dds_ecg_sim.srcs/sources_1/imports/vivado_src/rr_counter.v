// ============================================================
// RR 间期计数器：数两次 R 波之间过了多少个采样点
//   rr_count = 最近一次完整心跳的采样点数（72次/分 ≈ 208）
//   rr_valid = 1 拍高脉冲，表示 rr_count 已更新
// 心率换算（在 Python 做）：BPM = 60 * 250 / rr_count
// ============================================================
module rr_counter #(
    parameter CNT_W = 16
)(
    input  wire clk,
    input  wire rst_n,
    input  wire sig_valid,             // 采样节拍
    input  wire r_detect,              // R 波脉冲
    output reg  [CNT_W-1:0] rr_count,
    output reg              rr_valid
);
    reg [CNT_W-1:0] cnt;

    always @(posedge clk) begin
        if (!rst_n) begin
            cnt      <= {CNT_W{1'b0}};
            rr_count <= {CNT_W{1'b0}};
            rr_valid <= 1'b0;
        end
        else begin
            rr_valid <= 1'b0;
            if (sig_valid) begin
                if (r_detect) begin
                    rr_count <= cnt;    // 锁存：这次心跳用了多少采样点
                    rr_valid <= 1'b1;
                    cnt      <= 1;      // 从当前 R 采样点重新数
                end
                else begin
                    cnt <= cnt + 1'b1;
                end
            end
        end
    end
endmodule