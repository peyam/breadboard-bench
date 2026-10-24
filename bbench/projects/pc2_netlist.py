"""The PC-2 design, chip pin by chip pin (port of pc2sim/pc2_netlist.py; keep in step with it).

Conventions
- Every control line from the microcode EEPROMs is ACTIVE LOW (name ends _n). Each one
  has an LED wired from VCC through 2.2 kOhm, so the LED lights when the line is active.
- Registers load on the RISING edge of CLK. The step counter and the control-address
  latch change on the FALLING edge (they are clocked by CLK_n), so the control word only
  ever changes while CLK is low and is steady for the whole high half of each cycle.
- RAM is written only while CLK is high (WE = RI and CLK).
- The bus has a 10 kOhm pull-down on every line, so it reads 0 when nothing drives it.
- Parts as in the kit's bill of materials: every logic chip is 74HCT (TTL input levels,
  so the 555s and the memories, whose outputs are TTL levels, drive them safely), the
  timers are NE555, the RAM an AS6C62256 and the four ROMs AT28C256.
"""
from ..compat.pc2sim import Netlist
from . import pc2_roms as roms

B = [f"BUS{i}" for i in range(8)]


def build(control_images=None, display_image=None):
    if control_images is None:
        control_images = roms.control_images()
    if display_image is None:
        display_image = roms.display_image()
    N = Netlist()

    # ------------------------------------------------------------------ clock
    m = N.module("Clock")
    N.chip("U1", "NE555", m, "run clock (astable)", OUT="CLKRAW", TRIG="CT1", THR="CT1",
           DIS="DIS1", RESET="VCC", CTRL="CV1")
    N.part("R", m, {"1": "VCC", "2": "DIS1"}, "1k", note="astable R1")
    N.part("R", m, {"1": "DIS1", "2": "POT1"}, "1k", note="astable R2 (minimum)")
    N.part("VR", m, {"1": "POT1", "W": "CT1", "3": "CT1"}, "1M lin", note="clock speed")
    N.part("JP", m, {"COM": "CT1", "SLOW": "CTS", "FAST": "CTF"}, note="speed range jumper")
    N.part("C", m, {"+": "CTS", "-": "GND"}, "1uF", note="slow range, 0.7-480 Hz")
    N.part("C", m, {"1": "CTF", "2": "GND"}, "100nF", note="fast range, 7-4800 Hz")
    N.part("C", m, {"1": "CV1", "2": "GND"}, "10nF", note="555 control-voltage decoupling")

    N.chip("U2", "NE555", m, "single-step pulse (monostable)", OUT="STEPPULSE", TRIG="STEPBTN",
           THR="CT2", DIS="CT2", RESET="VCC", CTRL="CV2")
    N.part("R", m, {"1": "VCC", "2": "STEPBTN"}, "10k", note="pull-up", board="Front panel")
    N.part("BTN", m, {"1": "STEPBTN", "2": "GND"}, note="STEP", board="Front panel")
    N.part("R", m, {"1": "VCC", "2": "CT2"}, "100k", note="monostable timing")
    N.part("C", m, {"+": "CT2", "-": "GND"}, "1uF", note="monostable timing, 110 ms")
    N.part("C", m, {"1": "CV2", "2": "GND"}, "10nF")

    N.chip("U3", "NE555", m, "run/step select (bistable debouncer)", OUT="RUNSEL", TRIG="SELRUN",
           RESET="SELSTEP", THR="GND", DIS="U3DIS", CTRL="CV3")
    N.part("R", m, {"1": "VCC", "2": "SELRUN"}, "10k", note="pull-up", board="Front panel")
    N.part("R", m, {"1": "VCC", "2": "SELSTEP"}, "10k", note="pull-up", board="Front panel")
    N.part("SPDT", m, {"COM": "GND", "RUN": "SELRUN", "STEP": "SELSTEP"}, note="RUN / STEP", board="Front panel")
    N.part("C", m, {"1": "CV3", "2": "GND"}, "10nF")

    N.chip("U4", "74HC04", m, "clock inverters", **{
        "1A": "RUNSEL", "1Y": "RUNSEL_n", "2A": "CLK", "2Y": "CLK_n", "3A": "RST", "3Y": "RST_n",
        "4A": "GND", "5A": "GND", "6A": "GND"})
    N.chip("U5", "74HC08", m, "clock select and halt", **{
        "1A": "CLKRAW", "1B": "RUNSEL", "1Y": "CK_RUN",
        "2A": "STEPPULSE", "2B": "RUNSEL_n", "2Y": "CK_STEP",
        "3A": "CK_SEL", "3B": "HLT_n", "3Y": "CLK",
        "4A": "GND", "4B": "GND"})
    N.chip("U6", "74HC32", m, "clock select", **{
        "1A": "CK_RUN", "1B": "CK_STEP", "1Y": "CK_SEL",
        "2A": "GND", "2B": "GND", "3A": "GND", "3B": "GND", "4A": "GND", "4B": "GND"})
    # RST is an asynchronous clear that runs to six boards beside CLK: a stiff 1 kOhm pull-down
    # and 10 nF at the button keep a coupled spike from clearing registers mid-run
    N.part("R", m, {"1": "RST", "2": "GND"}, "1k", note="pull-down", board="Front panel")
    N.part("C", m, {"1": "RST", "2": "GND"}, "10nF", note="reset line filter", board="Front panel")
    N.part("BTN", m, {"1": "VCC", "2": "RST"}, note="RESET", board="Front panel")
    N.led_source(m, "CLK", "1k", "yellow", "clock")

    # ------------------------------------------------------------------ bus
    m = N.module("Bus")
    N.part("RN", m, {"C": "GND", **{str(i + 1): B[i] for i in range(8)}}, "8 x 10k bussed",
           note="bus pull-downs", ref="RN1")
    for i in range(7, -1, -1):
        N.led_source(m, B[i], "1k", "red", f"bus {i}")

    # ------------------------------------------------------------------ A register
    m = N.module("A register")
    for ref, lo in (("U7", 0), ("U8", 4)):
        N.chip(ref, "74HC173", m, f"A bits {lo}-{lo+3}", M="GND", N="GND", CLK="CLK",
               G1="AI_n", G2="AI_n", CLR="RST",
               **{f"{k+1}D": B[lo + k] for k in range(4)},
               **{f"{k+1}Q": f"A{lo + k}" for k in range(4)})
    N.chip("U9", "74HC245", m, "A to bus", DIR="VCC", OE="AO_n",
           **{f"A{k+1}": f"A{k}" for k in range(8)}, **{f"B{k+1}": B[k] for k in range(8)})
    for k in range(7, -1, -1):
        N.led_source(m, f"A{k}", "1k", "red", f"A bit {k}")

    # ------------------------------------------------------------------ B register
    m = N.module("B register")
    for ref, lo in (("U10", 0), ("U11", 4)):
        N.chip(ref, "74HC173", m, f"B bits {lo}-{lo+3}", M="GND", N="GND", CLK="CLK",
               G1="BI_n", G2="BI_n", CLR="RST",
               **{f"{k+1}D": B[lo + k] for k in range(4)},
               **{f"{k+1}Q": f"B{lo + k}" for k in range(4)})
    for k in range(7, -1, -1):
        N.led_source(m, f"B{k}", "1k", "red", f"B bit {k}")

    # ------------------------------------------------------------------ ALU
    m = N.module("ALU")
    for ref, lo in (("U12", 0), ("U13", 4)):
        N.chip(ref, "74HC86", m, f"invert B bits {lo}-{lo+3} when subtracting",
               **{f"{k+1}A": f"B{lo + k}" for k in range(4)},
               **{f"{k+1}B": "SU" for k in range(4)},
               **{f"{k+1}Y": f"BX{lo + k}" for k in range(4)})
    N.chip("U14", "74HC283", m, "adder bits 0-3", C0="SU", C4="CMID",
           **{f"A{k+1}": f"A{k}" for k in range(4)}, **{f"B{k+1}": f"BX{k}" for k in range(4)},
           **{f"S{k+1}": f"E{k}" for k in range(4)})
    N.chip("U15", "74HC283", m, "adder bits 4-7", C0="CMID", C4="COUT",
           **{f"A{k+1}": f"A{k+4}" for k in range(4)}, **{f"B{k+1}": f"BX{k+4}" for k in range(4)},
           **{f"S{k+1}": f"E{k+4}" for k in range(4)})
    N.chip("U16", "74HC245", m, "ALU result to bus", DIR="VCC", OE="EO_n",
           **{f"A{k+1}": f"E{k}" for k in range(8)}, **{f"B{k+1}": B[k] for k in range(8)})
    for k in range(7, -1, -1):
        N.led_source(m, f"E{k}", "1k", "red", f"sum bit {k}")

    # ------------------------------------------------------------------ flags
    m = N.module("Flags")
    N.chip("U17", "74HC02", m, "zero detect, first stage", **{
        "1A": "E0", "1B": "E1", "1Y": "NZ01", "2A": "E2", "2B": "E3", "2Y": "NZ23",
        "3A": "E4", "3B": "E5", "3Y": "NZ45", "4A": "E6", "4B": "E7", "4Y": "NZ67"})
    N.chip("U18", "74HC08", m, "zero detect, second stage", **{
        "1A": "NZ01", "1B": "NZ23", "1Y": "Z0", "2A": "NZ45", "2B": "NZ67", "2Y": "Z1",
        "3A": "Z0", "3B": "Z1", "3Y": "ZERO", "4A": "GND", "4B": "GND"})
    N.chip("U19", "74HC173", m, "flags register (carry, zero)", M="GND", N="GND", CLK="CLK",
           G1="FI_n", G2="FI_n", CLR="RST", **{"1D": "COUT", "2D": "ZERO", "3D": "GND", "4D": "GND",
                                              "1Q": "FC", "2Q": "FZ"})
    N.led_source(m, "FC", "1k", "yellow", "carry flag")
    N.led_source(m, "FZ", "1k", "yellow", "zero flag")

    # ------------------------------------------------------------------ program counter
    m = N.module("Program counter")
    N.chip("U20", "74HC161", m, "program counter (clocked on the falling edge: TI notes that CE and LOAD may only change while its clock input is high)", CLR="RST_n", CLK="CLK_n", ENP="CE", ENT="CE",
           LOAD="J_n", A=B[0], B=B[1], C=B[2], D=B[3], QA="PC0", QB="PC1", QC="PC2", QD="PC3")
    N.chip("U21", "74HC245", m, "PC to bus", DIR="VCC", OE="CO_n",
           **{f"A{k+1}": f"PC{k}" for k in range(4)}, **{f"A{k+1}": "GND" for k in range(4, 8)},
           **{f"B{k+1}": B[k] for k in range(8)})
    for k in range(3, -1, -1):
        N.led_source(m, f"PC{k}", "1k", "green", f"PC bit {k}")

    # ------------------------------------------------------------------ memory address register
    m = N.module("Memory address")
    N.chip("U22", "74HC173", m, "memory address register", M="GND", N="GND", CLK="CLK",
           G1="MI_n", G2="MI_n", CLR="RST", **{f"{k+1}D": B[k] for k in range(4)},
           **{f"{k+1}Q": f"MAR{k}" for k in range(4)})
    N.chip("U23", "74HC157", m, "address select: MAR (run) or switches (program)", S="PROG", G="GND",
           **{f"{k+1}A": f"MAR{k}" for k in range(4)}, **{f"{k+1}B": f"ASW{k}" for k in range(4)},
           **{f"{k+1}Y": f"RA{k}" for k in range(4)})
    N.switch_bank(m, [f"ASW{k}" for k in range(4)], [f"address switch {k}" for k in range(4)], "S1", msb_first=True)
    for k in range(3, -1, -1):
        N.led_source(m, f"RA{k}", "1k", "yellow", f"address bit {k}")
    # PROGRAM / RUN is used as an on/off switch to +5 V with a 10 kOhm pull-down (its RUN leg is
    # not connected), so no slide switch, shorting or not, can ever join +5 V to GND
    N.part("SPDT", m, {"COM": "PROG", "PROG": "VCC", "RUN": "PROG_NC"}, note="PROGRAM / RUN", board="Front panel")
    N.part("R", m, {"1": "PROG", "2": "GND"}, "10k", note="pull-down", board="Front panel")
    N.led_source(m, "PROG", "1k", "yellow", "program mode", board="Front panel")

    # ------------------------------------------------------------------ RAM
    m = N.module("RAM")
    N.chip("U24", "AS6C62256", m, "RAM (16 of 32 768 bytes used)", CE="GND", OE="RAMOE_n", WE="RAMWE_n",
           **{f"A{k}": f"RA{k}" for k in range(4)}, **{f"A{k}": "GND" for k in range(4, 15)},
           **{f"IO{k}": f"RD{k}" for k in range(8)})
    N.chip("U25", "74HC245", m, "bus to/from RAM", DIR="RO_n", OE="PROG",
           **{f"A{k+1}": B[k] for k in range(8)}, **{f"B{k+1}": f"RD{k}" for k in range(8)})
    N.chip("U26", "74HC245", m, "data switches to RAM", DIR="VCC", OE="SWEN_n",
           **{f"A{k+1}": f"DSW{k}" for k in range(8)}, **{f"B{k+1}": f"RD{k}" for k in range(8)})
    N.chip("U27", "74HC00", m, "RAM write logic", **{
        "1A": "WRBTN_n", "1B": "WRBTN_n", "1Y": "WRITE",
        "2A": "RI_n", "2B": "RI_n", "2Y": "RI",
        "3A": "RI", "3B": "CLK", "3Y": "WEGATE_n",
        "4A": "GND", "4B": "GND"})
    N.chip("U28", "74HC157", m, "RAM control select: run or program", S="PROG", G="GND", **{
        "1A": "WEGATE_n", "1B": "WRBTN_n", "1Y": "RAMWE_n",
        "2A": "RO_n", "2B": "WRITE", "2Y": "RAMOE_n",
        "3A": "VCC", "3B": "WRBTN_n", "3Y": "SWEN_n",
        "4A": "GND", "4B": "GND"})
    N.part("R", m, {"1": "VCC", "2": "WRBTN_n"}, "10k", note="pull-up", board="Front panel")
    N.part("BTN", m, {"1": "WRBTN_n", "2": "GND"}, note="WRITE", board="Front panel")
    N.switch_bank(m, [f"DSW{k}" for k in range(8)], [f"data switch {k}" for k in range(8)], "S2", msb_first=True)
    for k in range(8):
        N.led_source(m, f"RD{7 - k}", "2.2k", "red", f"RAM data bit {7 - k}")

    # ------------------------------------------------------------------ instruction register
    m = N.module("Instruction register")
    N.chip("U29", "74HC173", m, "instruction register, operand (low nibble)", M="GND", N="GND",
           CLK="CLK", G1="II_n", G2="II_n", CLR="RST", **{f"{k+1}D": B[k] for k in range(4)},
           **{f"{k+1}Q": f"IRL{k}" for k in range(4)})
    N.chip("U30", "74HC173", m, "instruction register, opcode (high nibble)", M="GND", N="GND",
           CLK="CLK", G1="II_n", G2="II_n", CLR="RST", **{f"{k+1}D": B[k + 4] for k in range(4)},
           **{f"{k+1}Q": f"OP{k}" for k in range(4)})
    N.chip("U31", "74HC245", m, "operand to bus", DIR="VCC", OE="IO_n",
           **{f"A{k+1}": f"IRL{k}" for k in range(4)}, **{f"A{k+1}": "GND" for k in range(4, 8)},
           **{f"B{k+1}": B[k] for k in range(8)})
    for k in range(3, -1, -1):
        N.led_source(m, f"OP{k}", "1k", "sky", f"opcode bit {k}")
    for k in range(3, -1, -1):
        N.led_source(m, f"IRL{k}", "1k", "sky", f"operand bit {k}")

    # ------------------------------------------------------------------ output
    m = N.module("Output")
    N.chip("U32", "74HC377", m, "output register", E="OI_n", CLK="CLK",
           **{f"D{k}": B[k] for k in range(8)}, **{f"Q{k}": f"OUT{k}" for k in range(8)})
    N.chip("U33", "74HC173", m, "display mode register", M="GND", N="GND", CLK="CLK",
           G1="OI_n", G2="OI_n", CLR="RST", **{"1D": "IRL0", "2D": "IRL1", "3D": "GND", "4D": "GND",
                                               "1Q": "MODE0", "2Q": "MODE1"})
    N.chip("U34", "AT28C256", m, "display decoder ROM", image=display_image, CE="GND", OE="GND", WE="VCC",
           **{f"A{k}": f"OUT{k}" for k in range(8)}, A8="DIG0", A9="DIG1", A10="MODE0", A11="MODE1",
           A12="GND", A13="GND", A14="GND", **{f"IO{k}": f"SR{k}" for k in range(8)})
    m = N.module("Display")
    DRV = "Display driver"
    N.chip("U35", "74HC245", m, "segment drivers", board=DRV, DIR="VCC", OE="GND",
           **{f"A{k+1}": f"SR{k}" for k in range(8)}, **{f"B{k+1}": f"SEG{k}" for k in range(8)})
    N.chip("U36", "NE555", m, "display scan clock (astable, about 690 Hz)", board=DRV, OUT="SCANCLK",
           TRIG="CT4", THR="CT4", DIS="DIS4", RESET="VCC", CTRL="CV4")
    N.part("R", m, {"1": "VCC", "2": "DIS4"}, "1k", board=DRV)
    N.part("R", m, {"1": "DIS4", "2": "CT4"}, "10k", board=DRV)
    N.part("C", m, {"1": "CT4", "2": "GND"}, "100nF", board=DRV)
    N.part("C", m, {"1": "CV4", "2": "GND"}, "10nF", board=DRV)
    N.chip("U37", "74HC107", m, "digit counter", board=DRV, **{
        "1J": "VCC", "1K": "VCC", "1CLK": "SCANCLK", "1CLR": "VCC", "1Q": "DIG0",
        "2J": "VCC", "2K": "VCC", "2CLK": "DIG0", "2CLR": "VCC", "2Q": "DIG1"})
    N.chip("U38", "74HC139", m, "digit select", board=DRV, **{
        "1G": "GND", "1A": "DIG0", "1B": "DIG1",
        "1Y0": "DSEL0_n", "1Y1": "DSEL1_n", "1Y2": "DSEL2_n", "1Y3": "DSEL3_n",
        "2G": "VCC", "2A": "GND", "2B": "GND"})
    seg = "a b c d e f g dp".split()
    for k in range(8):
        N.part("R", m, {"1": f"SEG{k}", "2": f"SEGR{k}"}, "470", note=f"segment {seg[k]}")
    for d in (3, 2, 1, 0):
        N.part("R", m, {"1": f"DSEL{d}_n", "2": f"QB{d}"}, "2.2k", note=f"digit {d} base", board=DRV)
        N.part("Q", m, {"E": "VCC", "B": f"QB{d}", "C": f"DCOM{d}"}, "2N3906", note=f"digit {d} driver", board=DRV)
        N.part("DISP", m, {"CA": f"DCOM{d}", **{seg[k]: f"SEGR{k}" for k in range(8)}},
               "0.56in common anode", note=f"digit {d} ({['ones', 'tens', 'hundreds', 'sign'][d]})")
    for k in range(7, -1, -1):
        N.led_source("Output", f"OUT{k}", "1k", "red", f"output bit {k}")

    # ------------------------------------------------------------------ input
    m = N.module("Input")
    for ref, bank in (("U39", "A"), ("U40", "B")):
        N.chip(ref, "74HC245", m, f"input switches {bank} to bus", DIR="VCC", OE=f"XSEL{'AB'.index(bank)}_n",
               **{f"A{k+1}": f"IN{bank}{k}" for k in range(8)}, **{f"B{k+1}": B[k] for k in range(8)})
        N.switch_bank(m, [f"IN{bank}{k}" for k in range(8)], [f"input {bank} switch {k}" for k in range(8)],
                      "S3" if bank == "A" else "S4", msb_first=True)
    N.chip("U41", "74HC139", m, "input bank select", **{
        "1G": "XO_n", "1A": "IRL0", "1B": "GND", "1Y0": "XSEL0_n", "1Y1": "XSEL1_n",
        "2G": "VCC", "2A": "GND", "2B": "GND"})

    # ------------------------------------------------------------------ control
    m = N.module("Control")
    roms_lines = [
        ["HLT_n", "MI_n", "RI_n", "RO_n", "IO_n", "II_n", "AI_n", "AO_n"],
        ["EO_n", "SU_n", "BI_n", "OI_n", "CE_n", "CO_n", "J_n", "FI_n"],
        ["XO_n", "SR_n", None, None, None, None, None, None],
    ]
    caddr = {"A0": "STEP0", "A1": "STEP1", "A2": "STEP2", "A3": "LOP0", "A4": "LOP1", "A5": "LOP2",
             "A6": "LOP3", "A7": "LZ", "A8": "LC", **{f"A{k}": "GND" for k in range(9, 15)}}
    for i, ref in enumerate(("U42", "U43", "U44")):
        io = {f"IO{k}": net for k, net in enumerate(roms_lines[i]) if net}
        N.chip(ref, "AT28C256", m, f"microcode ROM {i}", image=control_images[i], CE="GND", OE="GND",
               WE="VCC", board="Control ROMs", **caddr, **io)
    N.chip("U45", "74HC161", m, board="Control sequencer", role="step counter", CLR="RST_n", CLK="CLK_n", A="GND", B="GND", C="GND",
           D="GND", ENP="VCC", ENT="VCC", LOAD="SR_n", QA="STEP0", QB="STEP1", QC="STEP2")
    N.chip("U46", "74HC174", m, board="Control sequencer", role="control address latch", CLR="RST_n", CLK="CLK_n", **{
        "1D": "OP0", "2D": "OP1", "3D": "OP2", "4D": "OP3", "5D": "FZ", "6D": "FC",
        "1Q": "LOP0", "2Q": "LOP1", "3Q": "LOP2", "4Q": "LOP3", "5Q": "LZ", "6Q": "LC"})
    N.chip("U47", "74HC04", m, board="Control sequencer", role="active-high copies of SU and CE", **{
        "1A": "SU_n", "1Y": "SU", "2A": "CE_n", "2Y": "CE",
        "3A": "GND", "4A": "GND", "5A": "GND", "6A": "GND"})
    N.chip("U48", "74HC138", m, board="Control sequencer", role="step display decoder", A="STEP0", B="STEP1", C="STEP2",
           G1="VCC", G2A="GND", G2B="GND", **{f"Y{k}": f"STEPY{k}_n" for k in range(8)})
    for k in range(8):
        N.led_sink(m, f"STEPY{k}_n", "1k", "green", f"step T{k}", board="Control sequencer")
    for line in [l for row in roms_lines for l in row if l]:
        N.led_sink(m, line, "2.2k", "green", f"control {line[:-2]}",
                   board="Control sequencer" if line in ("XO_n", "SR_n") else "Control ROMs")

    # one 100 nF decoupling capacitor at every chip, from its VCC pin to its own GND
    for ref, pc in list(N.chips.items()):
        N.part("C", pc.module, {"1": "VCC", "2": "GND"}, "100nF", note=f"decoupling {ref}",
               ref=f"CD{ref[1:]}", board=pc.board)
    # one bulk electrolytic across the supply on every board (100 uF at the power entry on the Bus board)
    for k, (board, module) in enumerate(BULK):
        cb = N.part("C", module, {"+": "VCC", "-": "GND"}, "100uF" if board == "Bus" else "10uF",
                    note="bulk supply capacitor", ref=f"CB{k + 1}", board=board)
        if board == "Bus":
            cb.rail_row = 59        # beside the power entry (USB-C breakout and fuse, rows 56-63)
    return N


# board -> the module its bulk capacitor is drawn with on the schematic sheets
BULK = [("Front panel", "Clock"), ("Clock", "Clock"), ("Bus", "Bus"), ("A register", "A register"),
        ("B register", "B register"), ("ALU", "ALU"), ("Flags", "Flags"), ("Memory address", "Memory address"),
        ("RAM", "RAM"), ("Program counter", "Program counter"), ("Instruction register", "Instruction register"),
        ("Input", "Input"), ("Output", "Output"), ("Display driver", "Display"), ("Display", "Display"),
        ("Control sequencer", "Control"), ("Control ROMs", "Control")]


CONTROL_LINES = ["HLT", "MI", "RI", "RO", "IO", "II", "AI", "AO", "EO", "SU", "BI", "OI",
                 "CE", "CO", "J", "FI", "XO", "SR"]
