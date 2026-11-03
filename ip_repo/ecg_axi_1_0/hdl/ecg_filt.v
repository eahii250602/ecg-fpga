`timescale 1ns / 1ps
//=============================================================================
// ecg_filt.v —— D4/D5 心电前置滤波链（50Hz 陷波 + 40Hz 低通）
//
// 结构：2 级双二阶（biquad）级联，Direct Form I，定点 Q2.14
//   级1：50Hz 陷波 (Q=10)   —— 挖掉工频干扰
//   级2：40Hz 低通 (Q=0.707) —— 压掉肌电等高频
//
// ★时序改版（v2，2026-11-03）：
//   v1 把"5 乘 + 5 加 + 移位 + 饱和 + 输出"全塞进一拍，实测 WNS = -6.363ns
//   （最差路径 16.143ns，17 级逻辑、11 个 CARRY4）。
//   v2 拆成每级 3 拍：
//     P1 乘法（DSP48 寄存） → P2 累加树 → P3 移位+饱和+更新历史
//   每级 3 拍，两级共 6 拍 = 96ns，只占 250Hz 采样间隔(4ms)的 2.4%
//
// 定点约定（与 sim/filt/filt_fixed_sim.py 逐位一致）：
//   y = (b0*x + b1*x1 + b2*x2 - a1*y1 - a2*y2 + 8192) >>> 14
//   +8192 是实现四舍五入；纯截断会引入直流偏置（实测会导致发散）
//=============================================================================
module ecg_filt (
    input  wire               clk,
    input  wire               rst,          // 同步复位，高有效
    input  wire               sample_tick,  // 单拍脉冲，250Hz
    input  wire signed [11:0] din,          // 原始心电（12 位有符号）
    output reg  signed [11:0] dout,         // 滤波后（12 位有符号）
    output reg                dout_valid    // dout 有效脉冲（单拍）
);

    localparam integer       FRAC = 14;
    localparam signed [35:0] HALF = 36'sd8192;      // 2^(FRAC-1)，四舍五入用

    //-------------------------------------------------------------------------
    // 系数（Q2.14：真实值 = 整数 / 16384）
    //-------------------------------------------------------------------------
    // 级1：50Hz 陷波
    localparam signed [15:0] N_B0 = 16'sh3D18;      //  0.95460580
    localparam signed [15:0] N_B1 = 16'shDA3E;      // -0.58997883
    localparam signed [15:0] N_B2 = 16'sh3D18;      //  0.95460580
    localparam signed [15:0] N_A1 = 16'shDA3E;      // -0.58997883
    localparam signed [15:0] N_A2 = 16'sh3A31;      //  0.90921159

    // 级2：40Hz 低通
    localparam signed [15:0] L_B0 = 16'sh094D;      //  0.14531568
    localparam signed [15:0] L_B1 = 16'sh129A;      //  0.29063136
    localparam signed [15:0] L_B2 = 16'sh094D;      //  0.14531568
    localparam signed [15:0] L_A1 = 16'shD50E;      // -0.67099121
    localparam signed [15:0] L_A2 = 16'sh1025;      //  0.25225392

    //-------------------------------------------------------------------------
    // 饱和函数
    //   输入 22 位：36 位累加器右移 14 位后只剩 22 位有效（±2^21），
    //   在这里做 22 位比较，比拿 36 位去比省 14 位进位链
    //-------------------------------------------------------------------------
    function signed [15:0] sat16;
        input signed [21:0] v;
        begin
            if (v > 22'sd32767)
                sat16 = 16'sd32767;
            else if (v < -22'sd32768)
                sat16 = -16'sd32768;
            else
                sat16 = v[15:0];
        end
    endfunction

    function signed [11:0] sat12;
        input signed [15:0] v;
        begin
            if (v > 16'sd2047)
                sat12 = 12'sd2047;
            else if (v < -16'sd2048)
                sat12 = -12'sd2048;
            else
                sat12 = v[11:0];
        end
    endfunction

    //-------------------------------------------------------------------------
    // 流水线有效标志：vld[k] = 采样脉冲延迟 k 拍
    //   vld[0] 级1 P1   vld[1] 级1 P2   vld[2] 级1 P3
    //   vld[3] 级2 P1   vld[4] 级2 P2   vld[5] 级2 P3（同时锁存 dout）
    //-------------------------------------------------------------------------
    reg [6:0] vld;

    always @(posedge clk) begin
        if (rst)
            vld <= 7'd0;
        else
            vld <= {vld[5:0], sample_tick};
    end

    //=========================================================================
    // 级 1：50Hz 陷波
    //=========================================================================
    wire signed [15:0] s1_x = {{4{din[11]}}, din};   // 12 位符号扩展成 16 位

    reg  signed [15:0] s1_xr;                        // 锁存的样本值（P3 更新历史用）
    reg  signed [15:0] s1_x1, s1_x2;                 // x[n-1], x[n-2]
    reg  signed [15:0] s1_y1, s1_y2;                 // y[n-1], y[n-2]
    reg  signed [31:0] s1_p0, s1_p1, s1_p2, s1_p3, s1_p4;
    reg  signed [35:0] s1_acc;

    wire signed [21:0] s1_sh   = (s1_acc + HALF) >>> FRAC;
    wire signed [15:0] s1_ynew = sat16(s1_sh);

    // ---- P1：5 个乘法（会被放入 DSP48 的乘法寄存器）----
    always @(posedge clk) begin
        if (rst) begin
            s1_xr <= 16'sd0;
            s1_p0 <= 32'sd0; s1_p1 <= 32'sd0; s1_p2 <= 32'sd0;
            s1_p3 <= 32'sd0; s1_p4 <= 32'sd0;
        end else if (vld[0]) begin
            s1_xr <= s1_x;
            s1_p0 <= N_B0 * s1_x;      // b0 × 今天的输入
            s1_p1 <= N_B1 * s1_x1;     // b1 × 昨天的输入
            s1_p2 <= N_B2 * s1_x2;     // b2 × 前天的输入
            s1_p3 <= N_A1 * s1_y1;     // a1 × 昨天的输出（回音）
            s1_p4 <= N_A2 * s1_y2;     // a2 × 前天的输出（回音）
        end
    end

    // ---- P2：36 位累加树（留 4 位余量防溢出绕回）----
    always @(posedge clk) begin
        if (rst)
            s1_acc <= 36'sd0;
        else if (vld[1])
            s1_acc <= s1_p0 + s1_p1 + s1_p2 - s1_p3 - s1_p4;
    end

    // ---- P3：四舍五入 + 右移 + 饱和 + 历史寄存器移位 ----
    always @(posedge clk) begin
        if (rst) begin
            s1_x1 <= 16'sd0;
            s1_x2 <= 16'sd0;
            s1_y1 <= 16'sd0;
            s1_y2 <= 16'sd0;
        end else if (vld[2]) begin
            s1_x2 <= s1_x1;            // 昨天的变成前天
            s1_x1 <= s1_xr;            // 今天的变成昨天
            s1_y2 <= s1_y1;
            s1_y1 <= s1_ynew;
        end
    end

    // s1_y1 就是级1 对当前样本的输出（P3 拍冻结在寄存器里）
    wire signed [15:0] s1_out = s1_y1;

    //=========================================================================
    // 级 2：40Hz 低通（结构与级1 完全相同，只换系数和流水线位置）
    //=========================================================================
    wire signed [15:0] s2_x = s1_out;

    reg  signed [15:0] s2_xr;
    reg  signed [15:0] s2_x1, s2_x2;
    reg  signed [15:0] s2_y1, s2_y2;
    reg  signed [31:0] s2_p0, s2_p1, s2_p2, s2_p3, s2_p4;
    reg  signed [35:0] s2_acc;

    wire signed [21:0] s2_sh   = (s2_acc + HALF) >>> FRAC;
    wire signed [15:0] s2_ynew = sat16(s2_sh);

    always @(posedge clk) begin
        if (rst) begin
            s2_xr <= 16'sd0;
            s2_p0 <= 32'sd0; s2_p1 <= 32'sd0; s2_p2 <= 32'sd0;
            s2_p3 <= 32'sd0; s2_p4 <= 32'sd0;
        end else if (vld[3]) begin
            s2_xr <= s2_x;
            s2_p0 <= L_B0 * s2_x;
            s2_p1 <= L_B1 * s2_x1;
            s2_p2 <= L_B2 * s2_x2;
            s2_p3 <= L_A1 * s2_y1;
            s2_p4 <= L_A2 * s2_y2;
        end
    end

    always @(posedge clk) begin
        if (rst)
            s2_acc <= 36'sd0;
        else if (vld[4])
            s2_acc <= s2_p0 + s2_p1 + s2_p2 - s2_p3 - s2_p4;
    end

    always @(posedge clk) begin
        if (rst) begin
            s2_x1 <= 16'sd0;
            s2_x2 <= 16'sd0;
            s2_y1 <= 16'sd0;
            s2_y2 <= 16'sd0;
        end else if (vld[5]) begin
            s2_x2 <= s2_x1;
            s2_x1 <= s2_xr;
            s2_y2 <= s2_y1;
            s2_y1 <= s2_ynew;
        end
    end

    //=========================================================================
    // 输出：饱和到 12 位
    //=========================================================================
    always @(posedge clk) begin
        if (rst) begin
            dout       <= 12'sd0;
            dout_valid <= 1'b0;
        end else if (vld[5]) begin
            dout       <= sat12(s2_ynew);
            dout_valid <= 1'b1;
        end else begin
            dout_valid <= 1'b0;
        end
    end

endmodule