// ============================================================
// vitals_hw.v —— 生理量硬件统计（v6a，第 2 版：全流水）
//
// v1 的时序失败（WNS −4.102 ns，32 个端点违例）
//   最差路径：pt_rr_last → hrv_sum_drr2[29]，13.95 ns / 16 级逻辑 / 9 CARRY4 / 2 DSP48
//   根因有两个：
//     ① 求绝对值与平方写在同一表达式里，综合实例化了 **两个乘法器**
//        (drr[15] ? -drr : drr) * (drr[15] ? -drr : drr)
//     ② 平方、40 位累加、以及泄漏积分器的"减 + 加"全部挤在一拍
//   修法：所有乘法与宽加法各自独立成拍；累加器位宽 40 → 32（见下）
//
// 位宽依据
//   x² 最大 2048² = 4.19e6；泄漏积分稳态 ≈ x²×256 ≈ 1.07e9 → 31 位
//   故 acc 取 32 位（余 4 倍），比 40 位少 8 级进位链
//   Σrr² 最大 64×207² ≈ 2.7e6、Σrr 最大 64×207 ≈ 1.3e4 → 32 位足够
// ============================================================
`timescale 1ns / 1ps

module vitals_hw (
    input  wire               clk,
    input  wire               rst,
    input  wire               sample_tick,      // 250 Hz

    input  wire signed [11:0] x_in,             // 陷波前
    input  wire signed [11:0] x_out,            // 滤波后

    input  wire               det_pulse,        // R 峰检测（单拍）
    input  wire [15:0]        rr_samples,       // 本次 RR（采样点数）

    input  wire               clear,            // PS 读完后清零

    output reg  [1:0]         sqi_level,
    output reg  [31:0]        acc_in_q,
    output reg  [31:0]        acc_out_q,
    output reg  [15:0]        hrv_n,
    output reg  [31:0]        hrv_sum_rr,
    output reg  [31:0]        hrv_sum_rr2,
    output reg  [31:0]        hrv_sum_drr2,
    output reg                hrv_ready
);

    // ------------------------------------------------------------
    // 采样节拍延时链：P1 平方 → P2 差分 → P3 累加
    // ------------------------------------------------------------
    reg st1, st2, st3;
    always @(posedge clk) begin
        if (rst) begin st1<=0; st2<=0; st3<=0; end
        else     begin st1<=sample_tick; st2<=st1; st3<=st2; end
    end

    // ---- P1：平方（DSP 内部寄存输出）----
    reg signed [23:0] sq_in_r, sq_out_r;
    always @(posedge clk) begin
        if (rst) begin sq_in_r <= 0; sq_out_r <= 0; end
        else if (sample_tick) begin
            sq_in_r  <= x_in  * x_in;
            sq_out_r <= x_out * x_out;
        end
    end

    // ---- P2：算"增量 = 平方值 − 衰减量"（一个减法器）----
    reg signed [31:0] d_in_r, d_out_r;
    reg        [31:0] acc_in, acc_out;

    always @(posedge clk) begin
        if (rst) begin d_in_r <= 0; d_out_r <= 0; end
        else if (st1) begin
            d_in_r  <= $signed(sq_in_r)  - $signed({1'b0, acc_in[31:8]});   // acc/256
            d_out_r <= $signed(sq_out_r) - $signed({1'b0, acc_out[31:8]});
        end
    end

    // ---- P3：累加（一个加法器）----
    always @(posedge clk) begin
        if (rst) begin
            acc_in <= 0; acc_out <= 0;
            acc_in_q <= 0; acc_out_q <= 0;
        end else if (st2) begin
            acc_in  <= acc_in  + d_in_r;
            acc_out <= acc_out + d_out_r;
        end else if (st3) begin
            acc_in_q  <= acc_in;        // 再寄存一拍，供 PS 稳定读取
            acc_out_q <= acc_out;
        end
    end

    // ------------------------------------------------------------
    // 质量分级：用比较代替除法
    //   取高 24 位比较（低位对阈值判定无影响），把比较位宽从 32 降到 24
    //   SQI≥80% ⟺ ao×5 ≥ ai×4；≥50% ⟺ ao×2 ≥ ai；≥20% ⟺ ao×5 ≥ ai
    // ------------------------------------------------------------
    wire [23:0] ai = acc_in_q[31:8];
    wire [23:0] ao = acc_out_q[31:8];
    wire [25:0] ao5 = {ao, 2'b00} + ao;      // ×5
    wire [25:0] ai4 = {ai, 2'b00};           // ×4
    wire [24:0] ao2 = {ao, 1'b0};            // ×2

    always @(posedge clk) begin
        if (rst)                  sqi_level <= 2'd0;
        else if (acc_in_q < 32'd1024) sqi_level <= 2'd0;      // 输入无能量
        else if (ao5 >= ai4)      sqi_level <= 2'd3;          // ≥80%
        else if (ao2 >= ai)       sqi_level <= 2'd2;          // ≥50%
        else if (ao5 >= ai)       sqi_level <= 2'd1;          // ≥20%
        else                      sqi_level <= 2'd0;
    end

    // ------------------------------------------------------------
    // HRV：一次检测用 4 拍完成（心跳间隔约 3.2M 拍，绰绰有余）
    //   S1 锁存 rr 与 rr−rr_prev，并算 rr²           （1 DSP）
    //   S2 取绝对值，Σrr 与 Σrr² 累加
    //   S3 算 |d|²                                   （1 DSP）
    //   S4 ΣΔrr² 累加，n++
    // ------------------------------------------------------------
    reg [2:0]  hs;
    reg [15:0] rr_lat;
    reg signed [16:0] d_r;
    reg [16:0] d_abs;
    reg [31:0] rr2_r, dsq_r;
    reg [15:0] rr_prev;
    reg        rr_prev_vld;
    reg [2:0]  octl;

    wire signed [16:0] d_new = $signed({1'b0, rr_samples}) - $signed({1'b0, rr_prev});

    always @(posedge clk) begin
        if (rst || clear) begin
            hs <= 3'd0; rr_lat <= 0; d_r <= 0; d_abs <= 0;
            rr2_r <= 0; dsq_r <= 0;
            hrv_n <= 0; hrv_sum_rr <= 0; hrv_sum_rr2 <= 0; hrv_sum_drr2 <= 0;
            hrv_ready <= 0; rr_prev <= 0; rr_prev_vld <= 0;
        end else begin
            case (hs)
            3'd0: if (det_pulse && !hrv_ready && rr_samples != 16'd0) begin
                      rr_lat <= rr_samples;
                      d_r    <= rr_prev_vld ? d_new : 17'sd0;
                      rr2_r  <= rr_samples * rr_samples;        // DSP
                      rr_prev <= rr_samples;
                      rr_prev_vld <= 1'b1;
                      hs <= 3'd1;
                  end
            3'd1: begin
                      d_abs <= d_r[16] ? (~d_r + 17'd1) : d_r;  // |d|
                      hrv_sum_rr  <= hrv_sum_rr + {16'd0, rr_lat};
                      hrv_sum_rr2 <= hrv_sum_rr2 + rr2_r;
                      hs <= 3'd2;
                  end
            3'd2: begin
                      dsq_r <= d_abs * d_abs;                   // DSP
                      hs <= 3'd3;
                  end
            3'd3: begin
                      hrv_sum_drr2 <= hrv_sum_drr2 + dsq_r;
                      hrv_n <= hrv_n + 16'd1;
                      if (hrv_n == 16'd63) hrv_ready <= 1'b1;
                      hs <= 3'd0;
                  end
            default: hs <= 3'd0;
            endcase
        end
    end

endmodule
