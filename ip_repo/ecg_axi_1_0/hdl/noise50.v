`timescale 1ns / 1ps
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
        sin_tab[  0] = 12'sd0;
        sin_tab[  1] = 12'sd25;
        sin_tab[  2] = 12'sd50;
        sin_tab[  3] = 12'sd75;
        sin_tab[  4] = 12'sd100;
        sin_tab[  5] = 12'sd125;
        sin_tab[  6] = 12'sd150;
        sin_tab[  7] = 12'sd175;
        sin_tab[  8] = 12'sd200;
        sin_tab[  9] = 12'sd224;
        sin_tab[ 10] = 12'sd249;
        sin_tab[ 11] = 12'sd273;
        sin_tab[ 12] = 12'sd297;
        sin_tab[ 13] = 12'sd321;
        sin_tab[ 14] = 12'sd345;
        sin_tab[ 15] = 12'sd369;
        sin_tab[ 16] = 12'sd392;
        sin_tab[ 17] = 12'sd415;
        sin_tab[ 18] = 12'sd438;
        sin_tab[ 19] = 12'sd460;
        sin_tab[ 20] = 12'sd483;
        sin_tab[ 21] = 12'sd505;
        sin_tab[ 22] = 12'sd526;
        sin_tab[ 23] = 12'sd548;
        sin_tab[ 24] = 12'sd569;
        sin_tab[ 25] = 12'sd590;
        sin_tab[ 26] = 12'sd610;
        sin_tab[ 27] = 12'sd630;
        sin_tab[ 28] = 12'sd650;
        sin_tab[ 29] = 12'sd669;
        sin_tab[ 30] = 12'sd688;
        sin_tab[ 31] = 12'sd706;
        sin_tab[ 32] = 12'sd724;
        sin_tab[ 33] = 12'sd742;
        sin_tab[ 34] = 12'sd759;
        sin_tab[ 35] = 12'sd775;
        sin_tab[ 36] = 12'sd792;
        sin_tab[ 37] = 12'sd807;
        sin_tab[ 38] = 12'sd822;
        sin_tab[ 39] = 12'sd837;
        sin_tab[ 40] = 12'sd851;
        sin_tab[ 41] = 12'sd865;
        sin_tab[ 42] = 12'sd878;
        sin_tab[ 43] = 12'sd891;
        sin_tab[ 44] = 12'sd903;
        sin_tab[ 45] = 12'sd915;
        sin_tab[ 46] = 12'sd926;
        sin_tab[ 47] = 12'sd936;
        sin_tab[ 48] = 12'sd946;
        sin_tab[ 49] = 12'sd955;
        sin_tab[ 50] = 12'sd964;
        sin_tab[ 51] = 12'sd972;
        sin_tab[ 52] = 12'sd980;
        sin_tab[ 53] = 12'sd987;
        sin_tab[ 54] = 12'sd993;
        sin_tab[ 55] = 12'sd999;
        sin_tab[ 56] = 12'sd1004;
        sin_tab[ 57] = 12'sd1009;
        sin_tab[ 58] = 12'sd1013;
        sin_tab[ 59] = 12'sd1016;
        sin_tab[ 60] = 12'sd1019;
        sin_tab[ 61] = 12'sd1021;
        sin_tab[ 62] = 12'sd1023;
        sin_tab[ 63] = 12'sd1024;
        sin_tab[ 64] = 12'sd1024;
        sin_tab[ 65] = 12'sd1024;
        sin_tab[ 66] = 12'sd1023;
        sin_tab[ 67] = 12'sd1021;
        sin_tab[ 68] = 12'sd1019;
        sin_tab[ 69] = 12'sd1016;
        sin_tab[ 70] = 12'sd1013;
        sin_tab[ 71] = 12'sd1009;
        sin_tab[ 72] = 12'sd1004;
        sin_tab[ 73] = 12'sd999;
        sin_tab[ 74] = 12'sd993;
        sin_tab[ 75] = 12'sd987;
        sin_tab[ 76] = 12'sd980;
        sin_tab[ 77] = 12'sd972;
        sin_tab[ 78] = 12'sd964;
        sin_tab[ 79] = 12'sd955;
        sin_tab[ 80] = 12'sd946;
        sin_tab[ 81] = 12'sd936;
        sin_tab[ 82] = 12'sd926;
        sin_tab[ 83] = 12'sd915;
        sin_tab[ 84] = 12'sd903;
        sin_tab[ 85] = 12'sd891;
        sin_tab[ 86] = 12'sd878;
        sin_tab[ 87] = 12'sd865;
        sin_tab[ 88] = 12'sd851;
        sin_tab[ 89] = 12'sd837;
        sin_tab[ 90] = 12'sd822;
        sin_tab[ 91] = 12'sd807;
        sin_tab[ 92] = 12'sd792;
        sin_tab[ 93] = 12'sd775;
        sin_tab[ 94] = 12'sd759;
        sin_tab[ 95] = 12'sd742;
        sin_tab[ 96] = 12'sd724;
        sin_tab[ 97] = 12'sd706;
        sin_tab[ 98] = 12'sd688;
        sin_tab[ 99] = 12'sd669;
        sin_tab[100] = 12'sd650;
        sin_tab[101] = 12'sd630;
        sin_tab[102] = 12'sd610;
        sin_tab[103] = 12'sd590;
        sin_tab[104] = 12'sd569;
        sin_tab[105] = 12'sd548;
        sin_tab[106] = 12'sd526;
        sin_tab[107] = 12'sd505;
        sin_tab[108] = 12'sd483;
        sin_tab[109] = 12'sd460;
        sin_tab[110] = 12'sd438;
        sin_tab[111] = 12'sd415;
        sin_tab[112] = 12'sd392;
        sin_tab[113] = 12'sd369;
        sin_tab[114] = 12'sd345;
        sin_tab[115] = 12'sd321;
        sin_tab[116] = 12'sd297;
        sin_tab[117] = 12'sd273;
        sin_tab[118] = 12'sd249;
        sin_tab[119] = 12'sd224;
        sin_tab[120] = 12'sd200;
        sin_tab[121] = 12'sd175;
        sin_tab[122] = 12'sd150;
        sin_tab[123] = 12'sd125;
        sin_tab[124] = 12'sd100;
        sin_tab[125] = 12'sd75;
        sin_tab[126] = 12'sd50;
        sin_tab[127] = 12'sd25;
        sin_tab[128] = 12'sd0;
        sin_tab[129] = -12'sd25;
        sin_tab[130] = -12'sd50;
        sin_tab[131] = -12'sd75;
        sin_tab[132] = -12'sd100;
        sin_tab[133] = -12'sd125;
        sin_tab[134] = -12'sd150;
        sin_tab[135] = -12'sd175;
        sin_tab[136] = -12'sd200;
        sin_tab[137] = -12'sd224;
        sin_tab[138] = -12'sd249;
        sin_tab[139] = -12'sd273;
        sin_tab[140] = -12'sd297;
        sin_tab[141] = -12'sd321;
        sin_tab[142] = -12'sd345;
        sin_tab[143] = -12'sd369;
        sin_tab[144] = -12'sd392;
        sin_tab[145] = -12'sd415;
        sin_tab[146] = -12'sd438;
        sin_tab[147] = -12'sd460;
        sin_tab[148] = -12'sd483;
        sin_tab[149] = -12'sd505;
        sin_tab[150] = -12'sd526;
        sin_tab[151] = -12'sd548;
        sin_tab[152] = -12'sd569;
        sin_tab[153] = -12'sd590;
        sin_tab[154] = -12'sd610;
        sin_tab[155] = -12'sd630;
        sin_tab[156] = -12'sd650;
        sin_tab[157] = -12'sd669;
        sin_tab[158] = -12'sd688;
        sin_tab[159] = -12'sd706;
        sin_tab[160] = -12'sd724;
        sin_tab[161] = -12'sd742;
        sin_tab[162] = -12'sd759;
        sin_tab[163] = -12'sd775;
        sin_tab[164] = -12'sd792;
        sin_tab[165] = -12'sd807;
        sin_tab[166] = -12'sd822;
        sin_tab[167] = -12'sd837;
        sin_tab[168] = -12'sd851;
        sin_tab[169] = -12'sd865;
        sin_tab[170] = -12'sd878;
        sin_tab[171] = -12'sd891;
        sin_tab[172] = -12'sd903;
        sin_tab[173] = -12'sd915;
        sin_tab[174] = -12'sd926;
        sin_tab[175] = -12'sd936;
        sin_tab[176] = -12'sd946;
        sin_tab[177] = -12'sd955;
        sin_tab[178] = -12'sd964;
        sin_tab[179] = -12'sd972;
        sin_tab[180] = -12'sd980;
        sin_tab[181] = -12'sd987;
        sin_tab[182] = -12'sd993;
        sin_tab[183] = -12'sd999;
        sin_tab[184] = -12'sd1004;
        sin_tab[185] = -12'sd1009;
        sin_tab[186] = -12'sd1013;
        sin_tab[187] = -12'sd1016;
        sin_tab[188] = -12'sd1019;
        sin_tab[189] = -12'sd1021;
        sin_tab[190] = -12'sd1023;
        sin_tab[191] = -12'sd1024;
        sin_tab[192] = -12'sd1024;
        sin_tab[193] = -12'sd1024;
        sin_tab[194] = -12'sd1023;
        sin_tab[195] = -12'sd1021;
        sin_tab[196] = -12'sd1019;
        sin_tab[197] = -12'sd1016;
        sin_tab[198] = -12'sd1013;
        sin_tab[199] = -12'sd1009;
        sin_tab[200] = -12'sd1004;
        sin_tab[201] = -12'sd999;
        sin_tab[202] = -12'sd993;
        sin_tab[203] = -12'sd987;
        sin_tab[204] = -12'sd980;
        sin_tab[205] = -12'sd972;
        sin_tab[206] = -12'sd964;
        sin_tab[207] = -12'sd955;
        sin_tab[208] = -12'sd946;
        sin_tab[209] = -12'sd936;
        sin_tab[210] = -12'sd926;
        sin_tab[211] = -12'sd915;
        sin_tab[212] = -12'sd903;
        sin_tab[213] = -12'sd891;
        sin_tab[214] = -12'sd878;
        sin_tab[215] = -12'sd865;
        sin_tab[216] = -12'sd851;
        sin_tab[217] = -12'sd837;
        sin_tab[218] = -12'sd822;
        sin_tab[219] = -12'sd807;
        sin_tab[220] = -12'sd792;
        sin_tab[221] = -12'sd775;
        sin_tab[222] = -12'sd759;
        sin_tab[223] = -12'sd742;
        sin_tab[224] = -12'sd724;
        sin_tab[225] = -12'sd706;
        sin_tab[226] = -12'sd688;
        sin_tab[227] = -12'sd669;
        sin_tab[228] = -12'sd650;
        sin_tab[229] = -12'sd630;
        sin_tab[230] = -12'sd610;
        sin_tab[231] = -12'sd590;
        sin_tab[232] = -12'sd569;
        sin_tab[233] = -12'sd548;
        sin_tab[234] = -12'sd526;
        sin_tab[235] = -12'sd505;
        sin_tab[236] = -12'sd483;
        sin_tab[237] = -12'sd460;
        sin_tab[238] = -12'sd438;
        sin_tab[239] = -12'sd415;
        sin_tab[240] = -12'sd392;
        sin_tab[241] = -12'sd369;
        sin_tab[242] = -12'sd345;
        sin_tab[243] = -12'sd321;
        sin_tab[244] = -12'sd297;
        sin_tab[245] = -12'sd273;
        sin_tab[246] = -12'sd249;
        sin_tab[247] = -12'sd224;
        sin_tab[248] = -12'sd200;
        sin_tab[249] = -12'sd175;
        sin_tab[250] = -12'sd150;
        sin_tab[251] = -12'sd125;
        sin_tab[252] = -12'sd100;
        sin_tab[253] = -12'sd75;
        sin_tab[254] = -12'sd50;
        sin_tab[255] = -12'sd25;
    end

    wire signed [11:0] sin_v = sin_tab[idx];

    // ---- 流水第 1 拍：乘法（放进 DSP48 的乘法寄存器）----
    //   v1 把"乘法+叠加+饱和"塞在一拍，实测 WNS = -2.395ns（24 个端点违例，
    //   源点 u_noise/sel[0]）。这里拆成 3 拍，每拍只做一件事。
    reg signed [27:0] prod_r;

    always @(posedge clk) begin
        if (rst) prod_r <= 28'sd0;
        else     prod_r <= sin_v * $signed({1'b0, amp});   // 12 位 x 16 位
    end

    // ---- 流水第 2 拍：右移还原 + 叠加 + 饱和 ----
    wire signed [17:0] nval = prod_r[27:10];               // >>> 10 还原成 LSB
    wire signed [17:0] sum  = din + nval;

    reg signed [11:0] mix_r;

    always @(posedge clk) begin
        if (rst)
            mix_r <= 12'sd0;
        else if (sum > 18'sd2047)
            mix_r <= 12'sd2047;                            // 饱和
        else if (sum < -18'sd2048)
            mix_r <= -12'sd2048;
        else
            mix_r <= sum[11:0];
    end

    // ---- 流水第 3 拍：选择（纯 1 级 LUT 的旁路开关）----
    //   总延迟 3 拍 = 48ns，对 250Hz 采样（4ms）而言可忽略
    always @(posedge clk) begin
        if (rst) dout <= 12'sd0;
        else     dout <= en ? mix_r : din;
    end

endmodule
