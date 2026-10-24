# Companion files for *The Breadboard Computer*

| Folder | What it is |
|---|---|
| `pc2kit/` | The book's Python tools: `pc2.py` (PC-2 emulator and assembler), `pc2tools.py` (listings, traces), `prove.py` (checks every program and builds the ROM images). Run `python3 prove.py` from this folder. |
| `hardware/` | The chip-level model of PC-2: netlist, breadboard layout and checker, simulator and tests (`python3 test_hw.py`). |
| `programmer/` | The EEPROM programmer sketch for a Nano-compatible board (compatible with Arduino®), with the PC-2 ROM images built in. Derived from Ben Eater's MIT-licensed programmer. |
| `kit/` | The PC-2 kit bill of materials (LibreOffice/Excel). |

The same Python scripts also run in Breadboard Bench's **Code** tab, with nothing to install.
