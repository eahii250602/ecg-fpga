"""
心电波形模板生成器
输出两个文件：
  ecg_256x12.coe   —— 给 Vivado 的 Block Memory Generator 导入用
  ecg_256x12.mem   —— 纯 16 进制数值，给 testbench 用 $readmemh 读取
每个心跳周期 256 个点，12 位无符号偏移码（2048 = 基线）
"""
import numpy as np

# ---------------- 参数 ----------------
N_SAMPLES = 256          # 一个心跳周期的采样点数（= 查找表深度）
BPM       = 72           # 模拟心率：72 次/分
                                          # 心电频率 = 72/60 = 1.2 Hz
ROM_BITS  = 12           # 12 位无符号，偏移码
OFFSET    = 1 << (ROM_BITS - 1)           # 2048 = 零基线
FULLSCALE = (1 << (ROM_BITS - 1)) - 1     # 2047

# ---------------- 心电成分定义 ----------------
#   (幅度相对R, 时间中心μ[秒], 标准差σ[秒])
COMPONENTS = [
    ('P',  0.12,  0.20, 0.025),
    ('Q', -0.10,  0.375, 0.008),
    ('R',  1.00,  0.40, 0.010),
    ('S', -0.22,  0.425, 0.010),
    ('T',  0.30,  0.60, 0.055),
]

def gaussian(t, amp, mu, sigma):
    return amp * np.exp(-((t - mu) ** 2) / (2 * sigma ** 2))

def build_ecg():
    period = 60.0 / BPM                        # 一个心动周期时长（秒）
    t = np.linspace(0, period, N_SAMPLES, endpoint=False)

    sig = np.zeros(N_SAMPLES)
    for name, amp, mu, sigma in COMPONENTS:
        sig += gaussian(t, amp, mu * period, sigma * period)

    # 归一化到 [-1, 1]，然后映射成 12 位偏移码
    sig = sig / np.max(np.abs(sig))
    code = np.round(sig * FULLSCALE + OFFSET).astype(int)
    code = np.clip(code, 0, (1 << ROM_BITS) - 1)
    return code

def write_coe(code, path):
    """Vivado Block Memory Generator 的 .coe 格式"""
    with open(path, 'w') as f:
        f.write("memory_initialization_radix=16;\n")
        f.write("memory_initialization_vector=\n")
        for i, v in enumerate(code):
            sep = ";" if i == len(code) - 1 else ","
            f.write(f"{v:03X}{sep}\n")

def write_mem(code, path):
    """每行一个 16 进制数，给 $readmemh 用"""
    with open(path, 'w') as f:
        for v in code:
            f.write(f"{v:03X}\n")

if __name__ == "__main__":
    code = build_ecg()
    write_coe(code, "ecg_256x12.coe")
    write_mem(code, "ecg_256x12.mem")

    print(f"生成完成：{N_SAMPLES} 个点，{ROM_BITS} 位")
    print(f"  最大值 {code.max()}  最小值 {code.min()}  基线 {OFFSET}")
    print(f"  对应心率 {BPM} 次/分 -> 心电基频 {BPM/60:.2f} Hz")
    print(f"  R 波位置：第 {int(np.argmax(code))} 个点")
    print(f"  文件：ecg_256x12.coe / ecg_256x12.mem")