"""ROM images burned into PC-2's four AT28C256 EEPROMs.

Control ROMs: built from the microcode table in pc2.py (one control word per
carry/zero/opcode/step address). The hardware lines are ACTIVE LOW, so every bit
is inverted here: 0 in the ROM = line active.

Display ROM: address = value (A0-A7) | digit (A8-A9) | mode (A10-A11).
Data bit k drives segment a, b, c, d, e, f, g, dp (k = 0..7). The display is common
anode, so a segment lights when its bit is 0.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pc2  # noqa: E402

SIZE = 32768

SEG = {"0": 0x3F, "1": 0x06, "2": 0x5B, "3": 0x4F, "4": 0x66, "5": 0x6D, "6": 0x7D, "7": 0x07,
       "8": 0x7F, "9": 0x6F, "A": 0x77, "B": 0x7C, "C": 0x39, "D": 0x5E, "E": 0x79, "F": 0x71,
       "-": 0x40, " ": 0x00}


def control_images():
    imgs = [bytearray([0xFF]) * SIZE for _ in range(3)]
    for addr, word in pc2.ROM.items():
        for k in range(3):
            imgs[k][addr] = (~(word >> (8 * k))) & 0xFF
    return imgs


def display_text(value, mode):
    """The four characters shown, left to right, exactly as the ROM encodes them."""
    if mode == 0:
        s = str(value)
    elif mode == 1:
        s = str(value - 256 if value > 127 else value)
    elif mode == 2:
        s = f"{value:02X}"
    else:
        s = ""
    return s.rjust(4)


def display_image():
    img = bytearray([0xFF]) * SIZE
    for mode in range(4):
        for value in range(256):
            text = display_text(value, mode)
            for dig in range(4):            # digit 0 = rightmost
                ch = text[3 - dig]
                img[value | dig << 8 | mode << 10] = (~SEG[ch]) & 0xFF
    return img


def write_bins(folder):
    os.makedirs(folder, exist_ok=True)
    for i, img in enumerate(control_images()):
        open(os.path.join(folder, f"pc2_microcode_rom{i}.bin"), "wb").write(img)
    open(os.path.join(folder, "pc2_display_rom.bin"), "wb").write(display_image())


if __name__ == "__main__":
    write_bins(sys.argv[1] if len(sys.argv) > 1 else "roms")
