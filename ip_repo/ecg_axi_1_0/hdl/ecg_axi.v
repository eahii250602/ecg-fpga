
`timescale 1 ns / 1 ps

	module ecg_axi #
	(
		// Users to add parameters here
		// ---- 用户设计参数（可在例化 / 仿真时覆盖）----
		parameter integer       CLK_FREQ_HZ = 100_000_000,  // PL 时钟频率（PS 的 FCLK_CLK0）
		parameter integer       SAMPLE_FREQ = 250,          // 心电采样率 (Hz)
		parameter integer       THRESHOLD   = 1200,         // R 波阈值（★整数型：带位宽/signed 声明会被
		                                                    //   IP 包装层当向量、值渲染成字符串"1200"，
		                                                    //   进而被 Verilog 截断成 48 —— 见 L-15）
		parameter integer       BLANK_LEN   = 50,           // 不响应期（采样点数）
		parameter integer       ROM_AW      = 8,            // 波形表地址位宽
		// User parameters ends
		// Do not modify the parameters beyond this line


		// Parameters of Axi Slave Bus Interface S00_AXI
		parameter integer C_S00_AXI_DATA_WIDTH	= 32,
		parameter integer C_S00_AXI_ADDR_WIDTH	= 5
	)
	(
		// Users to add ports here
		// 【集成说明】本 IP 对外只暴露 AXI 接口。
		//   整条心电链（DDS→250Hz采样→阈值比较→R波检测→RR计数）都在 IP 内部，
		//   数据出入只通过 AXI 寄存器（Python 读写）。
		// User ports ends
		// Do not modify the ports beyond this line


		// Ports of Axi Slave Bus Interface S00_AXI
		input wire  s00_axi_aclk,
		input wire  s00_axi_aresetn,
		input wire [C_S00_AXI_ADDR_WIDTH-1 : 0] s00_axi_awaddr,
		input wire [2 : 0] s00_axi_awprot,
		input wire  s00_axi_awvalid,
		output wire  s00_axi_awready,
		input wire [C_S00_AXI_DATA_WIDTH-1 : 0] s00_axi_wdata,
		input wire [(C_S00_AXI_DATA_WIDTH/8)-1 : 0] s00_axi_wstrb,
		input wire  s00_axi_wvalid,
		output wire  s00_axi_wready,
		output wire [1 : 0] s00_axi_bresp,
		output wire  s00_axi_bvalid,
		input wire  s00_axi_bready,
		input wire [C_S00_AXI_ADDR_WIDTH-1 : 0] s00_axi_araddr,
		input wire [2 : 0] s00_axi_arprot,
		input wire  s00_axi_arvalid,
		output wire  s00_axi_arready,
		output wire [C_S00_AXI_DATA_WIDTH-1 : 0] s00_axi_rdata,
		output wire [1 : 0] s00_axi_rresp,
		output wire  s00_axi_rvalid,
		input wire  s00_axi_rready
	);

	// ============================================================
	// 【派生常量】由上面的用户参数自动算出，不要手改
	//   TICK_DIV = CLK_FREQ_HZ / SAMPLE_FREQ
	//             = 100_000_000 / 250 = 400000  → 250Hz 采样
	//   仿真时把 CLK_FREQ_HZ 覆盖成 1_250_000，则 TICK_DIV = 5000
	// ============================================================
	localparam integer TICK_DIV = CLK_FREQ_HZ / SAMPLE_FREQ;

	// ============================================================
	// 【内部信号】AXI 从机  ↔  心电信号链
	// ============================================================
	wire [31:0]        ftw_from_axi;      // Python 写 0x00 → 送 DDS 的 ftw
	wire [31:0]        rr_count_to_axi;   // RR 计数 → Python 读 0x08
	wire [15:0]        rr_count_raw;      // rr_counter 的 16 位原始输出
	wire [31:0]        wave_addr_from_axi; // ★V4 Python 写 0x04 → 波形读地址
	wire [31:0]        wave_data_to_axi;   // ★V4 波形数据 → Python 读 0x0C
	wire signed [11:0] ecg_wave;          // DDS 输出的心电波形
	wire [ROM_AW-1:0]  addr_dbg;          // ROM 表地址（调试观察用）
	wire               sample_tick;       // 250Hz 采样节拍
	wire               above;             // 超阈值标志
	wire               r_detect;          // R 波脉冲
	wire               rr_valid;          // RR 值更新标志

	// ★H2 新增：PT 链与 AXI 之间的连线
	wire [31:0] rr_pt_to_axi;     // PT 的 RR → 读 0x18
	wire [31:0] det_cnt_to_axi;   // PT 检测数 → 读 0x1C
	wire        r_detect_pt;      // PT 检出的 R 波脉冲
	wire [15:0] r_index_pt;       // PT 输出的 R 波序号（本 IP 内部未使用）
	wire [31:0] pt_sum_dbg;       // ★调试：PT 滑动和（临时写进波形缓冲）

	// ★D4/D5 新增：滤波链（陷波 50Hz + 低通 40Hz）
	wire signed [11:0] ecg_filt_out;      // 滤波后的心电波形
	wire               filt_valid;        // 滤波结果有效（单拍，暂未使用）
	wire [31:0]        filt_ctl_from_axi; // Python 写 0x10：bit0=缓冲用滤波, bit1=PT 用滤波

// Instantiation of Axi Bus Interface S00_AXI
	ecg_axi_slave_lite_v1_0_S00_AXI # ( 
		.C_S_AXI_DATA_WIDTH(C_S00_AXI_DATA_WIDTH),
		.C_S_AXI_ADDR_WIDTH(C_S00_AXI_ADDR_WIDTH)
	) ecg_axi_slave_lite_v1_0_S00_AXI_inst (
		.S_AXI_ACLK(s00_axi_aclk),
		.S_AXI_ARESETN(s00_axi_aresetn),
		.S_AXI_AWADDR(s00_axi_awaddr),
		.S_AXI_AWPROT(s00_axi_awprot),
		.S_AXI_AWVALID(s00_axi_awvalid),
		.S_AXI_AWREADY(s00_axi_awready),
		.S_AXI_WDATA(s00_axi_wdata),
		.S_AXI_WSTRB(s00_axi_wstrb),
		.S_AXI_WVALID(s00_axi_wvalid),
		.S_AXI_WREADY(s00_axi_wready),
		.S_AXI_BRESP(s00_axi_bresp),
		.S_AXI_BVALID(s00_axi_bvalid),
		.S_AXI_BREADY(s00_axi_bready),
		.S_AXI_ARADDR(s00_axi_araddr),
		.S_AXI_ARPROT(s00_axi_arprot),
		.S_AXI_ARVALID(s00_axi_arvalid),
		.S_AXI_ARREADY(s00_axi_arready),
		.S_AXI_RDATA(s00_axi_rdata),
		.S_AXI_RRESP(s00_axi_rresp),
		.S_AXI_RVALID(s00_axi_rvalid),
		.S_AXI_RREADY(s00_axi_rready),
		.reg_ftw(ftw_from_axi),           // ← 写 0x00 的值，接到 DDS 的 ftw
		.reg_rr_count(rr_count_to_axi),   // ← RR 计数（★这里补了逗号！）
		.reg_wave_addr(wave_addr_from_axi), // ★V4 波形读地址（Python 写 0x04）
		.reg_wave_data(wave_data_to_axi),   // ★V4 波形数据（Python 读 0x0C）
		.reg_rr_pt(rr_pt_to_axi),           // ★H2 PT 的 RR → 0x18
		.reg_det_cnt(det_cnt_to_axi),       // ★H2 PT 检测数 → 0x1C
		.reg_filt_ctl(filt_ctl_from_axi)    // ★D4/D5 滤波选择 ← 0x10
	);

	// ============================================================
	// 【用户逻辑】心电信号链（5 级流水，全部在 AXI 时钟域）
	//   写 0x00(FTW) → ①DDS生成波形 → ②250Hz采样 → ③阈值比较
	//                → ④R波检测 → ⑤RR计数 → 读 0x08(rr_count)
	// ============================================================

	// ---- ① DDS 心电波形发生器（内部例化 ecg_rom 查找表）----
	dds_ecg #(
		.AW       (ROM_AW)
	) u_dds (
		.clk      (s00_axi_aclk),
		.rst_n    (s00_axi_aresetn),
		.ftw      (ftw_from_axi),
		.ecg_wave (ecg_wave),
		.addr_dbg (addr_dbg)
	);

	// ---- ①.4 【D4/D5 新增】50Hz 工频干扰注入（测试用，默认关闭）----
	//   0x10.bit2 = 1 开启注入；0x10[23:8] = 幅度（单位 LSB，0~2047）
	//   关闭时 ecg_mix 恒等于 ecg_wave（完全旁路，行为与旧版一致）
	wire signed [11:0] ecg_mix;

	// ---- ①.3b 【D3 接入】主机样本模式 ----------------------------------
	//   0x10.bit3 = 1 → 信号源改为 0x00 的低 12 位（有符号样本），DDS 输出被忽略
	//   用途：把真实 XADC 采到的波形灌进硬件滤波链 / PT，而不是只走软件
	//   注意：进入该模式后 0x00 不再表示 FTW；退出（bit3=0）即恢复 DDS
	//   默认 bit3 = 0 → 行为与旧版完全一致（无回归）
	wire signed [11:0] src_wave = filt_ctl_from_axi[3]
	                            ? $signed(ftw_from_axi[11:0])
	                            : ecg_wave;

	noise50 u_noise (
		.clk  (s00_axi_aclk),
		.rst  (~s00_axi_aresetn),
		.en   (filt_ctl_from_axi[2]),
		.amp  (filt_ctl_from_axi[23:8]),
		.din  (src_wave),
		.dout (ecg_mix)
	);

	// ---- ①.5 【D4/D5 新增】滤波链：陷波 50Hz → 低通 40Hz ----
	//   定点 Q2.14、2 级 biquad 级联、Direct Form I、每级 3 拍流水（共 6 拍）
	//   注意：有 6 个时钟的流水延迟（96ns），对 RR 间隔与波形形状无影响
	//   仿真实证：sim/filt/compare_rtl.py → 2000/2000 与 Python 模型逐位相同
	ecg_filt u_filt (
		.clk         (s00_axi_aclk),
		.rst         (~s00_axi_aresetn),
		.sample_tick (sample_tick),
		.din         (ecg_mix),
		.dout        (ecg_filt_out),
		.dout_valid  (filt_valid)
	);

	// Python 写 0x10 选择：bit0 → 波形缓冲；bit1 → PT 输入
	//   默认全 0 = 都走原始波形，与旧版本行为完全一致
	wire signed [11:0] pt_in  = filt_ctl_from_axi[1] ? ecg_filt_out : ecg_mix;
	wire        [11:0] buf_in = filt_ctl_from_axi[0] ? ecg_filt_out : ecg_mix;

	// ---- ② 采样节拍生成：100MHz ÷ 400000 = 250Hz ----
	tick_gen #(
		.DIV      (TICK_DIV)
	) u_tick (
		.clk      (s00_axi_aclk),
		.rst_n    (s00_axi_aresetn),
		.tick     (sample_tick)
	);

	// ---- ③ 阈值比较：波形是否超过 1200 ----
	assign above = (ecg_wave > THRESHOLD);

	// ---- ④ R 波检测状态机（固定阈值 + 200ms 不响应期）----
	r_detect #(
		.BLANK_LEN(BLANK_LEN)
	) u_det (
		.clk      (s00_axi_aclk),
		.rst_n    (s00_axi_aresetn),
		.sig_valid(sample_tick),
		.above    (above),
		.r_detect (r_detect)
	);

	// ---- ⑤ RR 间期计数器 ----
	rr_counter #(
		.CNT_W    (16)
	) u_rr (
		.clk      (s00_axi_aclk),
		.rst_n    (s00_axi_aresetn),
		.sig_valid(sample_tick),
		.r_detect (r_detect),
		.rr_count (rr_count_raw),
		.rr_valid (rr_valid)
	);

	// ---- 位宽对齐：16 位 rr_count → 32 位 AXI 读数据（高位补 0）----
	assign rr_count_to_axi = {16'd0, rr_count_raw};

	// ============================================================
	// 【H2 新增】Pan-Tompkins 检测链（DDS 波形 → PT → RR/检测计数）
	//   0x18 = PT 的 RR 间隔（两个 R 波之间的 250Hz tick 数）
	//   0x1C = PT 累计检测数
	// ============================================================
	reg  [15:0] pt_rr_last;
	reg  [15:0] pt_prev_r;
	reg         pt_have_prev;
	reg  [31:0] pt_det_cnt;

	pt_chain u_pt (
		.clk      (s00_axi_aclk),
		.rst_n    (s00_axi_aresetn),
		.s_valid  (sample_tick),
		.s_data   (pt_in),
		.r_detect (r_detect_pt),
		.r_index  (r_index_pt),
		.sum_dbg  (pt_sum_dbg)
	);

	always @(posedge s00_axi_aclk) begin
		if (!s00_axi_aresetn) begin
			pt_rr_last   <= 16'd0;
			pt_prev_r    <= 16'd0;
			pt_have_prev <= 1'b0;
			pt_det_cnt   <= 32'd0;
		end
		else if (r_detect_pt) begin
			if (pt_have_prev)
				pt_rr_last <= r_index_pt - pt_prev_r;   // 两个 R 峰在采样时间轴上的差
			pt_prev_r    <= r_index_pt;
			pt_have_prev <= 1'b1;
			pt_det_cnt   <= pt_det_cnt + 32'd1;
		end
	end

	assign rr_pt_to_axi   = {16'd0, pt_rr_last};
	assign det_cnt_to_axi = pt_det_cnt;

	// ★调试：记录"自上一采样拍以来是否发生过检测"，写入缓冲时打标（值 ≥0x80000000）
	reg        pt_det_seen;
	reg [15:0] pt_det_idx;
	always @(posedge s00_axi_aclk) begin
		if (!s00_axi_aresetn) begin
			pt_det_seen <= 1'b0;
			pt_det_idx  <= 16'd0;
		end
		else begin
			if (r_detect_pt) begin
				pt_det_seen <= 1'b1;
				pt_det_idx  <= r_index_pt;
			end
			if (sample_tick) pt_det_seen <= 1'b0;
		end
	end

	// ============================================================
	// 【V4 用户逻辑】波形环形缓冲（"行车记录仪"）
	//   DDS 输出 → 每来一个 250Hz 采样节拍存入 BRAM
	//   → Python 通过 0x04(写索引) / 0x0C(读数据) 逐点读回并画图
	// ============================================================

	// ---- V4 常量（注意：用 localparam，不用 parameter！）----
	localparam integer WAVE_DEPTH = 1024;   // 缓冲深度：1024 点 = 4.1 秒（72BPM 约 5 个心跳）
	localparam integer WAVE_AW    = 10;     // 地址位宽 = log2(1024)

	// ---- 波形缓冲：1024 × 32bit（会被综合成 Block RAM）----
	reg [31:0] wave_mem [0:WAVE_DEPTH-1];

	// ---- 写指针：10 位，加到 1023 后自动回绕到 0（天然环形）----
	reg [WAVE_AW-1:0] wr_ptr;

	// ---- 写入数据：12 位有符号波形 → 符号扩展成 32 位 ----
	//      {20{ecg_wave[11]}} = 把符号位复制 20 份（负数补 1、正数补 0）
	// ★2026-11-03：调试通道已完成使命（证明 PT 全档 72~180BPM 跟随），恢复真实波形写入
	// ★2026-11-03(D4/D5)：缓冲写入源可由 0x10.bit0 选择"原始 / 滤波后"
	wire [31:0] wave_wr_data = {{20{buf_in[11]}}, buf_in};

	// ---- 读地址：只取 Python 写入值的低 10 位（超范围自动回绕）----
	wire [WAVE_AW-1:0] wave_rd_addr = wave_addr_from_axi[WAVE_AW-1:0];

	// ---- 同步读输出寄存器 ----
	reg [31:0] wave_rd_data;

	// ---- 写指针：独立 always，带复位，每来一个采样节拍 +1 ----
	always @(posedge s00_axi_aclk) begin
		if (!s00_axi_aresetn)   wr_ptr <= {WAVE_AW{1'b0}};
		else if (sample_tick)   wr_ptr <= wr_ptr + 1'b1;
	end

	// ---- RAM 本体：简单双口（一个写口 + 一个读口）----
	//      ★ 故意【不加复位】——这是 Vivado 推断 Block RAM 的标准模板
	always @(posedge s00_axi_aclk) begin
		if (sample_tick) wave_mem[wr_ptr] <= wave_wr_data;   // 写口（采样节拍写入）
		wave_rd_data     <= wave_mem[wave_rd_addr];          // 读口（同步读 → 推断为 BRAM）
	end

	// ---- 读出的数据送到 AXI 从机（Python 读 0x0C）----
	assign wave_data_to_axi = wave_rd_data;

	endmodule

	// ============================================================
	// 【H2 串行版·v2】pt_chain —— 阈值穿越开候选（抗平顶）
	// ============================================================
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
