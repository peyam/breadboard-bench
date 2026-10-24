"""The PC-2 starter programs of the book (as proven in pc2kit/prove.py)."""
from .pc2_emulator import asm

P = {}
P["ECHO"] = asm(["IN 0", "OUT 0", "HALT"])
P["COUNTDOWN"] = asm(["IN 0", "OUT 0", "SBI 1", "JC 1", "HALT"])
P["BIGGER"] = asm(["IN 1", "STORE 15", "IN 0", "STORE 14", "SUB 15", "JC 8",
                   "LOAD 15", "JUMP 9", "LOAD 14", "OUT 0", "HALT"])
P["ADD"] = asm(["IN 0", "STORE 15", "IN 1", "ADD 15", "JC 6", "OUT 0", "HALT"])

MUL = asm(["LOAD 14", "SBI 1", "JC 6", "LOAD 13", "OUT 0", "HALT",
           "STORE 14", "LOAD 13", "ADD 15", "STORE 13", "JUMP 0"])
DIV = asm(["LOAD 15", "SUB 14", "JC 6", "LOAD 13", "OUT 0", "HALT",
           "STORE 15", "LOAD 13", "ADI 1", "STORE 13", "JUMP 0"])
FIB = asm(["LOAD 14", "OUT 0", "ADD 15", "JC 10", "STORE 13", "LOAD 14",
           "STORE 15", "LOAD 13", "STORE 14", "JUMP 0", "HALT"])


def with_data(code, data):
    m = code + [0] * (16 - len(code))
    for addr, v in data.items():
        assert addr >= len(code), "data overlaps code"
        m[addr] = v
    return m


# ready-to-load images (16 bytes) with their notes, for the app's program menu
PROGRAMS = {
    "ECHO": {"mem": P["ECHO"], "notes": "Shows input bank A."},
    "COUNTDOWN": {"mem": P["COUNTDOWN"], "notes": "Counts down from input bank A to 0."},
    "ADD": {"mem": P["ADD"], "notes": "Adds banks A and B; the carry LED means the sum is over 255."},
    "BIGGER": {"mem": P["BIGGER"], "notes": "Shows the bigger of banks A and B."},
    "MULTIPLY": {"mem": with_data(MUL, {13: 0, 14: 6, 15: 7}), "notes": "7 x 6 (bytes 15 and 14)."},
    "DIVIDE": {"mem": with_data(DIV, {13: 0, 14: 7, 15: 100}), "notes": "100 / 7; remainder left in byte 15."},
    "FIBONACCI": {"mem": with_data(FIB, {13: 0, 14: 1, 15: 0}), "notes": "1 1 2 3 5 ... 233, then halts."},
}
