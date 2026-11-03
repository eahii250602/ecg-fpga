`timescale 1ns/1ps
// ============================================================
// pt_chain_serial.v —— Pan-Tompkins 五步流水线（串行 MAC 版）
//
// 为什么改串行：并行 61 乘法器版本在 100MHz 下时序 WNS = -98ns
//   （61 项乘法+加法树塞不进 10ns 周期）。250Hz 采样每 400000 个
//   时钟周期才来一个样本，用 1 个乘法器轮流算 61 个抽头完全够。
//
// 时序：每样本约 128 个时钟周期（61 抽头 × 2 拍 + 后级 7 拍）
// 用法：s_valid 打一拍（间隔必须 ≥ 128 个时钟；250Hz 下绰绰有余）
// 输出：r_detect 脉冲 + r_index（R 峰在采样时间轴上的序号）
// ============================================================
module pt_chain(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        s_valid,
    input  wire [11:0] s_data,
    output reg         r_detect,
    output reg  [15:0] r_index,
    output wire [31:0] sum_dbg       // 调试：滑动和（板上可写进波形缓冲观察）
);

    // ---- 系数表（Q1.15 内嵌，与 pt_bp_coef.mem 逐值一致）----
    reg signed [15:0] coef [0:60];
    initial begin
        coef[ 0] = 16'hFFF6; coef[ 1] = 16'hFFF1; coef[ 2] = 16'hFFEE; coef[ 3] = 16'hFFEF;
        coef[ 4] = 16'hFFF4; coef[ 5] = 16'h0000; coef[ 6] = 16'h0012; coef[ 7] = 16'h0027;
        coef[ 8] = 16'h003B; coef[ 9] = 16'h0045; coef[10] = 16'h003B; coef[11] = 16'h0011;
        coef[12] = 16'hFFBD; coef[13] = 16'hFF3C; coef[14] = 16'hFE8E; coef[15] = 16'hFDBE;
        coef[16] = 16'hFCE0; coef[17] = 16'hFC0E; coef[18] = 16'hFB6A; coef[19] = 16'hFB15;
        coef[20] = 16'hFB2C; coef[21] = 16'hFBC5; coef[22] = 16'hFCE5; coef[23] = 16'hFE85;
        coef[24] = 16'h0088; coef[25] = 16'h02C7; coef[26] = 16'h050D; coef[27] = 16'h0720;
        coef[28] = 16'h08CA; coef[29] = 16'h09DE; coef[30] = 16'h0A3D; coef[31] = 16'h09DE;
        coef[32] = 16'h08CA; coef[33] = 16'h0720; coef[34] = 16'h050D; coef[35] = 16'h02C7;
        coef[36] = 16'h0088; coef[37] = 16'hFE85; coef[38] = 16'hFCE5; coef[39] = 16'hFBC5;
        coef[40] = 16'hFB2C; coef[41] = 16'hFB15; coef[42] = 16'hFB6A; coef[43] = 16'hFC0E;
        coef[44] = 16'hFCE0; coef[45] = 16'hFDBE; coef[46] = 16'hFE8E; coef[47] = 16'hFF3C;
        coef[48] = 16'hFFBD; coef[49] = 16'h0011; coef[50] = 16'h003B; coef[51] = 16'h0045;
        coef[52] = 16'h003B; coef[53] = 16'h0027; coef[54] = 16'h0012; coef[55] = 16'h0000;
        coef[56] = 16'hFFF4; coef[57] = 16'hFFEF; coef[58] = 16'hFFEE; coef[59] = 16'hFFF1;
        coef[60] = 16'hFFF6;
    end

    // ---- 样本窗口（61 深）----
    reg signed [11:0] xb [0:60];

    // ---- 状态机 ----
    localparam S_IDLE = 3'd0, S_MUL = 3'd1, S_ADD = 3'd2, S_XF = 3'd3,
               S_D    = 3'd4, S_SQ  = 3'd5, S_SUM = 3'd6, S_PEAK = 3'd7;
    reg [2:0] st;
    reg [5:0] i;
    integer   k;

    reg signed [47:0] acc;
    reg signed [31:0] prod;

    reg signed [15:0] xf_r, xf_h1, xf_h2, xf_h3, xf_h4;
    reg signed [15:0] d_r;
    reg signed [31:0] sq_r;
    reg signed [31:0] sq_hist [0:37];
    reg signed [31:0] sum_r;
    reg signed [31:0] sum_s1, sum_s2;

    assign sum_dbg = sum_r;          // 调试输出：滑动和

    reg signed [31:0] spki, npki;
    wire signed [31:0] th1_w = npki + ((spki - npki) >>> 2);
    reg [15:0] last_r;

    reg        cand_active;
    reg signed [31:0] cand_val;
    reg [15:0] cand_idx;
    reg [5:0]  cand_age;

    reg [15:0] sidx;        // 已接收样本数
    reg [15:0] cur_idx;     // 当前样本序号

    // 带通输出（含饱和）
    wire signed [31:0] y32 = acc >>> 15;
    wire signed [15:0] xf_sat = (y32 > 32'sd4095)  ? 16'sd4095 :
                                (y32 < -32'sd4095) ? -16'sd4095 :
                                                     $signed(y32[15:0]);

    always @(posedge clk) begin
        if (!rst_n) begin
            st <= S_IDLE;
            for (k = 0; k < 61; k = k + 1) xb[k] <= 12'sd0;
            i <= 6'd0;
            acc <= 48'sd0;
            prod <= 32'sd0;
            xf_r <= 16'sd0; xf_h1 <= 16'sd0; xf_h2 <= 16'sd0; xf_h3 <= 16'sd0; xf_h4 <= 16'sd0;
            d_r <= 16'sd0; sq_r <= 32'sd0;
            sum_r <= 32'sd0; sum_s1 <= 32'sd0; sum_s2 <= 32'sd0;
            for (k = 0; k < 38; k = k + 1) sq_hist[k] <= 32'sd0;
            spki <= 32'sd278000;
            npki <= 32'sd92600;
            last_r <= 16'd0;
            r_detect <= 1'b0;
            r_index  <= 16'd0;
            cand_active <= 1'b0;
            cand_val    <= 32'sd0;
            cand_idx    <= 16'd0;
            cand_age    <= 6'd0;
            sidx <= 16'd0;
            cur_idx <= 16'd0;
        end
        else begin
            r_detect <= 1'b0;
            case (st)
                S_IDLE: begin
                    if (s_valid) begin
                        for (k = 60; k > 0; k = k - 1)
                            xb[k] <= xb[k-1];
                        xb[0]   <= s_data;
                        cur_idx <= sidx;
                        sidx    <= sidx + 16'd1;
                        i       <= 6'd0;
                        acc     <= 48'sd0;
                        st      <= S_MUL;
                    end
                end
                S_MUL: begin
                    prod <= coef[i] * xb[i];
                    st   <= S_ADD;
                end
                S_ADD: begin
                    acc <= acc + prod;
                    if (i == 6'd60) begin
                        st <= S_XF;
                    end
                    else begin
                        i  <= i + 6'd1;
                        st <= S_MUL;
                    end
                end
                S_XF: begin
                    xf_r <= xf_sat;
                    xf_h4 <= xf_h3; xf_h3 <= xf_h2; xf_h2 <= xf_h1; xf_h1 <= xf_r;
                    st   <= S_D;
                end
                S_D: begin
                    d_r <= (2 * xf_r + xf_h1 - xf_h3 - 2 * xf_h4) >>> 3;
                    st  <= S_SQ;
                end
                S_SQ: begin
                    sq_r <= d_r * d_r;
                    st   <= S_SUM;
                end
                S_SUM: begin
                    sum_r <= sum_r + sq_r - sq_hist[37];
                    for (k = 37; k > 0; k = k - 1)
                        sq_hist[k] <= sq_hist[k-1];
                    sq_hist[0] <= sq_r;
                    st <= S_PEAK;
                end
                S_PEAK: begin
                    // 候选起点：阈值穿越即开始（对"平顶/相等"免疫）
                    //   原"严格局部极大"条件在平方和出现相等样本时会永久漏拍。
                    if (!cand_active && sum_r > th1_w && (cur_idx - 16'd1 - last_r) >= 16'd50) begin
                        cand_active <= 1'b1;
                        cand_val    <= sum_r;
                        cand_idx    <= cur_idx;
                        cand_age    <= 6'd50;
                    end
                    else if (cand_active) begin
                        // 保持期内取最大（主峰覆盖先到的上升沿）
                        if (sum_r > cand_val) begin
                            cand_val <= sum_r;
                            cand_idx <= cur_idx;
                        end
                    end
                    else if (sum_s1 > sum_s2 && sum_s1 > sum_r) begin
                        // 无候选且未过阈值：只做噪声水平学习
                        npki <= npki + ((sum_s1 - npki) >>> 3);
                    end

                    if (cand_active) begin
                        if (cand_age == 6'd0) begin
                            r_detect <= 1'b1;
                            if (cand_idx >= 16'd51)
                                r_index <= cand_idx - 16'd50;
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
                    st <= S_IDLE;
                end
                default: st <= S_IDLE;
            endcase
        end
    end

endmodule
