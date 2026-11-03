#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xadc_selftest.py —— XADC 内部通道自测（D1 验收工具，v2）

v2 关键改动（2026-10-26 板上实测教训）：
    v1 直接读 /dev/mem，**没有先加载比特流** → PL 未配置时所有寄存器读回 0，
    与"数据通路故障"无法区分（板上实测全 0 的根因就在这里）。
    v2 按 ecg_monitor_serial.py 的成熟写法：
    先 Overlay 加载比特流 → 从 .hwh 取 XADC 物理地址 → 再读寄存器。

读 XADC 的通道，验证"ADC 硬核 → AXI → Python"整条通路：
    温度    (DRP 0x00) → 期望 30~60 ℃
    VCCINT  (DRP 0x01) → 期望 1.00 V ±5%
    VCCAUX  (DRP 0x02) → 期望 1.80 V ±5%
    V_P/V_N (DRP 0x03) → 板外专用对（J5 脚1/脚2）；悬空时读数不确定
    VAUX0   (DRP 0x10) → 辅助通道，PYNQ-Z2 上未接线，读数不作判据

寄存器映射依据 Vivado XADC Wizard 模板 axi_xadc_vhd.ttcl：
    0x00 SRR / 0x04 SR / 0x08 AOSR / 0x0C CONVSTR / 0x10 SYSMONRR
    0x200 + 4*n = DRP 寄存器 n（12 位码值在 [15:4]）

用法（板子串口，cwd 在脚本所在目录，ecg_bd.bit/hwh 同目录）：
    sudo -s
    source /etc/profile.d/pynq_venv.sh
    python3 xadc_selftest.py
"""
import sys
import os
import time

DEFAULT_XADC_BASE = 0x43C10000      # Address Editor 预期值（hwh 已实锤）
FALLBACK_ECG_BASE = 0x43C00000
VERSION_MAGIC     = 0xEC600004      # ecg_axi 的 VERSION 寄存器值（2026-11-03 更新：0xEC600004 为当前比特流）

# DRP 地址
DRP_TEMP   = 0x00
DRP_VCCINT = 0x01
DRP_VCCAUX = 0x02
DRP_VP_VN  = 0x03                  # V_P/V_N 专用对（J5 脚1/脚2）；若实测稳定≈1.0V 则实为 VCCBRAM
DRP_VAUX0  = 0x10                  # VAUX0 辅助通道（PYNQ-Z2 未接线，不作判据）

REG_OFFSET_BASE = 0x200            # 0x200 + 4*n


def code_to_temp(code):
    """XADC 温度公式：code × 503.975 / 4096 − 273.15 ℃"""
    return code * 503.975 / 4096.0 - 273.15


def code_to_volt_3v(code):
    """VCCINT / VCCAUX 等内部电压通道：code × 3.0 / 4096"""
    return code * 3.0 / 4096.0


def code_to_volt_1v(code):
    """单端模拟输入（V_P/V_N、VAUX）：code × 1.0 / 4096"""
    return code * 1.0 / 4096.0


def load_design(script_dir):
    """加载比特流并返回 (xadc_base, ecg_base)。失败返回 (None, None)。"""
    bitfile = os.path.join(script_dir, "ecg_bd.bit")
    print("[0] 加载比特流 / overlay ...")
    try:
        from pynq import Overlay
    except Exception as e:
        print("    !! 无法导入 pynq.Overlay: %s" % e)
        return None, None
    if not os.path.isfile(bitfile):
        print("    !! 找不到比特流文件: %s（.bit/.hwh 必须与脚本同目录）" % bitfile)
        return None, None

    ol = Overlay(bitfile)

    xadc_base = None
    ecg_base = None
    for name, info in ol.ip_dict.items():
        if "xadc" in name:
            try:
                xadc_base = info["phys_addr"]
            except (KeyError, TypeError):
                pass
            print("    XADC IP '%s' @ 0x%08X" % (name, xadc_base or DEFAULT_XADC_BASE))
        if "ecg_axi" in name:
            try:
                ecg_base = info["phys_addr"]
            except (KeyError, TypeError):
                pass
            print("    ecg_axi IP '%s' @ 0x%08X" % (name, ecg_base or FALLBACK_ECG_BASE))

    if xadc_base is None:
        print("    !! hwh 里没有 xadc IP，回退到 0x%08X" % DEFAULT_XADC_BASE)
        xadc_base = DEFAULT_XADC_BASE
    if ecg_base is None:
        ecg_base = FALLBACK_ECG_BASE
    return xadc_base, ecg_base


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    xadc_base, ecg_base = load_design(script_dir)
    if xadc_base is None:
        print("\n结论：❌ 比特流加载失败，未做任何寄存器读取。")
        print("     检查 ecg_bd.bit / ecg_bd.hwh 是否与脚本同目录。")
        return 2

    if len(sys.argv) > 1:
        xadc_base = int(sys.argv[1], 16)
        print("    （命令行指定 XADC 基地址 = 0x%08X）" % xadc_base)

    print("=" * 64)
    print(" XADC 自测  基地址 = 0x%08X" % xadc_base)
    print("=" * 64)

    from pynq import MMIO
    mm = MMIO(xadc_base, 0x400)

    # ---- 设计存活自检：读 ecg_axi 的 VERSION（证明 PL+AXI 真的在跑新设计）----
    ecg_mm = MMIO(ecg_base, 0x1000)
    ver = ecg_mm.read(0x14)
    print("\n[1] 设计存活自检: VERSION(0x%08X+0x14) = 0x%08X  (期望 0x%08X) -> %s"
          % (ecg_base, ver, VERSION_MAGIC, "PASS" if ver == VERSION_MAGIC else "FAIL"))
    if ver != VERSION_MAGIC:
        print("    !! 加载的不是本设计的比特流（或版本不对），先确认 .bit/.hwh 配对。")

    print("\n[2] 控制寄存器")
    print("    SR   (0x04) = 0x%08X" % mm.read(0x04))
    print("    AOSR (0x08) = 0x%08X" % mm.read(0x08))

    print("\n[3] 内部通道（等 300ms 让序列器转一圈）")
    time.sleep(0.3)
    results = []
    for label, addr, conv, lo, hi, unit in (
        ("温度  ", DRP_TEMP,   code_to_temp,     30.0,  60.0, "℃"),
        ("VCCINT", DRP_VCCINT, code_to_volt_3v,  0.95,  1.05, "V"),
        ("VCCAUX", DRP_VCCAUX, code_to_volt_3v,  1.71,  1.89, "V"),
    ):
        raw = mm.read(REG_OFFSET_BASE + 4 * addr)
        code = (raw >> 4) & 0xFFF
        val = conv(code)
        ok = lo <= val <= hi
        results.append(ok)
        print("    %-8s DRP0x%02X = 0x%08X  code=%4d  %8.3f %s  %s"
              % (label, addr, raw, code, val, unit,
                 "OK" if ok else "★超范围★"))

    print("\n[4] V_P/V_N（J5 专用对，DRP 0x03）与 VAUX0（DRP 0x10）通道判别")
    # J5 未接线时的判别法：
    #   0x03 读数乱跳/漂移  → 是悬空的 V_P/V_N（正常现象，证明映射对）
    #   0x03 稳定在 ~1.00 V → 它其实是 VCCBRAM，V_P/V_N 的 DRP 编号需再查
    for label, addr in (("V_P/VN", DRP_VP_VN), ("VAUX0 ", DRP_VAUX0)):
        raw = mm.read(REG_OFFSET_BASE + 4 * addr)
        code = (raw >> 4) & 0xFFF
        print("    %s DRP0x%02X = 0x%08X  code=%4d  %8.4f V"
              % (label, addr, raw, code, code_to_volt_1v(code)))

    print("\n[5] 稳定性（连续 5 次，每次间隔 200ms，看温度/VCCINT 是否漂移）")
    for i in range(5):
        t = code_to_temp((mm.read(REG_OFFSET_BASE + 4 * DRP_TEMP) >> 4) & 0xFFF)
        v = code_to_volt_3v((mm.read(REG_OFFSET_BASE + 4 * DRP_VCCINT) >> 4) & 0xFFF)
        print("    #%d  T=%7.3f ℃   VCCINT=%.4f V" % (i + 1, t, v))
        time.sleep(0.2)

    print("\n" + "=" * 64)
    if all(results):
        print(" 结论：✅ XADC 通路正常（ADC + AXI 寄存器 + Python 读取全通）")
    elif not any(results):
        print(" 结论：❌ 全部为 0 —— 转换没启动。检查 XADC 向导里")
        print("        Sequencer Mode 是否设为 Continuous、通道是否勾选。")
    else:
        print(" 结论：⚠ 部分通道异常，见上面标星的行")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
