
`timescale 1 ns / 1 ps

	module ecg_axi #
	(
		// Users to add parameters here
		// ---- 用户设计参数（可在例化 / 仿真时覆盖）----
		parameter integer       CLK_FREQ_HZ = 100_000_000,  // PL 时钟频率（PS 的 FCLK_CLK0）
		parameter integer       SAMPLE_FREQ = 250,          // 心电采样率 (Hz)
		parameter signed [11:0] THRESHOLD   = 12'sd1200,    // R 波阈值
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
		.reg_wave_data(wave_data_to_axi)    // ★V4 波形数据（Python 读 0x0C）
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
	wire [31:0] wave_wr_data = {{20{ecg_wave[11]}}, ecg_wave};

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