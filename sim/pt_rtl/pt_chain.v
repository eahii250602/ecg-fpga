`timescale 1ns/1ps
// ============================================================
// pt_chain.v —— Pan-Tompkins 五步流水线（H2 · RTL 版）
//
//   ① 带通 5~15Hz   ：61 抽头 FIR（Q1.15 系数，pt_bp_coef.mem）
//   ② 五点微分      ：(2x[n]+x[n-1]-x[n-3]-2x[n-4])/8
//   ③ 平方          ：d*d（只留能量）
//   ④ 38 点滑动和   ：150ms 窗口（250Hz × 0.15s），不做除法（阈值同尺度即可）
//   ⑤ 自适应双阈值  ：th1 = npki + (spki-npki)/4；200ms 不响应期
//
// 输入 ：s_valid（1 拍脉冲，每个 250Hz 采样一次）/ s_data（12 位有符号）
// 输出 ：r_detect（1 拍脉冲）/ r_index（R 峰在原始采样时间轴上的序号）
//        r_index 已减去 50 拍固定处理延迟（带通 30 + 微分 2 + 积分 18.5）
// 流水 ：每级 1 拍，输入到检测共 5 拍（相对 250Hz 采样间隔可忽略）
//
// 说明 ：spki/npki 初值按"12 位满幅心电"标定（本测试向量实测）；
//        真实心电换输入后需自适应学习，或改参数（见 progress.md D2 记录）。
// ============================================================
module pt_chain(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        s_valid,
    input  wire [11:0] s_data,
    output reg         r_detect,
    output reg  [15:0] r_index
);

    // ---------------- 系数表 ----------------
    reg signed [15:0] coef [0:60];
    initial begin
        $readmemh("pt_bp_coef.mem", coef);
    end

    // ---------------- 样本窗口（61 深）----------------
    reg signed [11:0] xb [0:60];
    integer i;

    // ---------------- 组合乘加 ----------------
    reg signed [47:0] acc;
    always @(*) begin
        acc = 48'sd0;
        for (i = 0; i < 61; i = i + 1)
            acc = acc + coef[i] * xb[i];
    end

    wire signed [31:0] y32 = acc >>> 15;
    wire signed [15:0] xf_sat = (y32 > 32'sd4095)  ? 16'sd4095 :
                                (y32 < -32'sd4095) ? -16'sd4095 :
                                                     $signed(y32[15:0]);

    // ---------------- 流水控制 ----------------
    reg        v0, v1, v2, v3, v4;
    reg [15:0] sidx;                       // 已接收样本计数
    reg [15:0] idx_pre, idx1, idx2, idx3, idx4;

    // ---------------- 各级寄存器 ----------------
    reg signed [15:0] xf_r, xf_h1, xf_h2, xf_h3, xf_h4;
    reg signed [15:0] d_r;
    reg signed [31:0] sq_r;
    reg signed [31:0] sq_hist [0:37];
    reg signed [31:0] sum_r;
    reg signed [31:0] sum_s1, sum_s2;

    // ---------------- 阈值 ----------------
    reg signed [31:0] spki, npki;
    wire signed [31:0] th1_w = npki + ((spki - npki) >>> 2);
    reg [15:0] last_r;

    // ---------------- 候选峰保持（200ms 内取最大再提交）----------------
    // 等价于 Python 的 local_maxima 的"50 拍内合并取最大"：
    // QRS 有两个子峰（R 上升/下降沿），先到的小峰不能先报，要等 50 拍取最大者。
    reg        cand_active;
    reg signed [31:0] cand_val;
    reg [15:0] cand_idx;
    reg [5:0]  cand_age;

    integer j;

    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < 61; i = i + 1) xb[i] <= 12'sd0;
            v0 <= 1'b0; v1 <= 1'b0; v2 <= 1'b0; v3 <= 1'b0; v4 <= 1'b0;
            sidx <= 16'd0; idx_pre <= 16'd0;
            idx1 <= 16'd0; idx2 <= 16'd0; idx3 <= 16'd0; idx4 <= 16'd0;
            xf_r <= 16'sd0; xf_h1 <= 16'sd0; xf_h2 <= 16'sd0; xf_h3 <= 16'sd0; xf_h4 <= 16'sd0;
            d_r <= 16'sd0; sq_r <= 32'sd0;
            sum_r <= 32'sd0; sum_s1 <= 32'sd0; sum_s2 <= 32'sd0;
            for (j = 0; j < 38; j = j + 1) sq_hist[j] <= 32'sd0;
            spki <= 32'sd278000;    // ≈ 0.6×12190×38（本测试向量标定）
            npki <= 32'sd92600;     // ≈ 0.2×12190×38
            last_r <= 16'd0;
            r_detect <= 1'b0;
            r_index  <= 16'd0;
            cand_active <= 1'b0;
            cand_val    <= 32'sd0;
            cand_idx    <= 16'd0;
            cand_age    <= 6'd0;
        end
        else begin
            r_detect <= 1'b0;

            // ---- S0：接收样本 ----
            if (s_valid) begin
                for (i = 60; i > 0; i = i - 1)
                    xb[i] <= xb[i-1];
                xb[0] <= s_data;
                idx_pre <= sidx;
                sidx    <= sidx + 16'd1;
                v0      <= 1'b1;
            end
            else
                v0 <= 1'b0;

            // ---- S1：带通 FIR ----
            if (v0) begin
                v1 <= 1'b1;
                idx1 <= idx_pre;
                xf_r <= xf_sat;
                xf_h4 <= xf_h3; xf_h3 <= xf_h2; xf_h2 <= xf_h1; xf_h1 <= xf_r;
            end
            else
                v1 <= 1'b0;

            // ---- S2：五点微分 ----
            if (v1) begin
                v2 <= 1'b1;
                idx2 <= idx1;
                d_r <= (2 * xf_r + xf_h1 - xf_h3 - 2 * xf_h4) >>> 3;
            end
            else
                v2 <= 1'b0;

            // ---- S3：平方 ----
            if (v2) begin
                v3 <= 1'b1;
                idx3 <= idx2;
                sq_r <= d_r * d_r;
            end
            else
                v3 <= 1'b0;

            // ---- S4：38 点滑动和 ----
            if (v3) begin
                v4 <= 1'b1;
                idx4 <= idx3;
                sum_r <= sum_r + sq_r - sq_hist[37];
                for (j = 37; j > 0; j = j - 1)
                    sq_hist[j] <= sq_hist[j-1];
                sq_hist[0] <= sq_r;
            end
            else
                v4 <= 1'b0;

            // ---- S5：峰值检测 + 自适应阈值 + 候选保持（v4 拍上做）----
            //   sum_r = integ(n)，sum_s1 = integ(n-1)，sum_s2 = integ(n-2)
            if (v4) begin
                // 1) 局部极大候选
                if (sum_s1 > sum_s2 && sum_s1 > sum_r) begin
                    if (cand_active) begin
                        // 保持期内：只替换更大的峰（QRS 主峰通常会覆盖先到的小峰）
                        if (sum_s1 > cand_val) begin
                            cand_val <= sum_s1;
                            cand_idx <= idx4 - 16'd1;
                        end
                    end
                    else if (sum_s1 > th1_w && (idx4 - 16'd1 - last_r) >= 16'd50) begin
                        // 过阈值且不在不响应期 → 开始保持一个候选
                        cand_active <= 1'b1;
                        cand_val    <= sum_s1;
                        cand_idx    <= idx4 - 16'd1;
                        cand_age    <= 6'd50;
                    end
                    else begin
                        // 低于阈值：学习噪声水平
                        npki <= npki + ((sum_s1 - npki) >>> 3);
                    end
                end

                // 2) 保持倒计时：50 拍（200ms）到点提交
                if (cand_active) begin
                    if (cand_age == 6'd0) begin
                        r_detect <= 1'b1;
                        if (cand_idx >= 16'd51)
                            r_index <= cand_idx - 16'd50;   // 减处理固定延迟
                        else
                            r_index <= 16'd0;
                        last_r <= cand_idx;
                        spki   <= spki + ((cand_val - spki) >>> 3);
                        cand_active <= 1'b0;
                    end
                    else begin
                        cand_age <= cand_age - 6'd1;
                    end
                end

                sum_s2 <= sum_s1;
                sum_s1 <= sum_r;
            end
        end
    end

endmodule
