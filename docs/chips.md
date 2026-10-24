# Chip reference

Every chip in the Breadboard Bench library. This file is generated from the chip
registry by `docs/make_chips_md.py`; do not edit it by hand.

Timing figures in the library are worst-case values at 4.5 V and 25 °C (LS parts: 5 V,
25 °C) from the datasheet linked in each row.

104 chips.

VIH is the input threshold for a 1 (HC 3.15 V, HCT and LS 2.0 V at 4.5 V; memories as their
datasheets give); — where the inputs are not logic inputs (the 555).

| Type | Description | Family | VIH | Package | Datasheet |
|---|---|---|---|---|---|
| 74HC00 | Quad 2-input NAND | HC | 3.15 V | DIP14 | [sn74hc00.pdf](https://www.ti.com/lit/ds/symlink/sn74hc00.pdf) |
| 74HCT00 | Quad 2-input NAND | HCT | 2 V | DIP14 | [sn74hct00.pdf](https://www.ti.com/lit/ds/symlink/sn74hct00.pdf) |
| 74HC02 | Quad 2-input NOR | HC | 3.15 V | DIP14 | [sn74hc02.pdf](https://www.ti.com/lit/ds/symlink/sn74hc02.pdf) |
| 74HCT02 | Quad 2-input NOR | HCT | 2 V | DIP14 | [sn74hct02.pdf](https://www.ti.com/lit/ds/symlink/sn74hct02.pdf) |
| 74HC04 | Hex inverter | HC | 3.15 V | DIP14 | [sn74hc04.pdf](https://www.ti.com/lit/ds/symlink/sn74hc04.pdf) |
| 74HCT04 | Hex inverter | HCT | 2 V | DIP14 | [sn74hct04.pdf](https://www.ti.com/lit/ds/symlink/sn74hct04.pdf) |
| 74HC08 | Quad 2-input AND | HC | 3.15 V | DIP14 | [sn74hc08.pdf](https://www.ti.com/lit/ds/symlink/sn74hc08.pdf) |
| 74HCT08 | Quad 2-input AND | HCT | 2 V | DIP14 | [sn74hct08.pdf](https://www.ti.com/lit/ds/symlink/sn74hct08.pdf) |
| 74HC10 | Triple 3-input NAND | HC | 3.15 V | DIP14 | [sn74hc10.pdf](https://www.ti.com/lit/ds/symlink/sn74hc10.pdf) |
| 74HCT10 | Triple 3-input NAND | HCT | 2 V | DIP14 | [cd74hct10.pdf](https://www.ti.com/lit/ds/symlink/cd74hct10.pdf) |
| 74HC11 | Triple 3-input AND | HC | 3.15 V | DIP14 | [sn74hc11.pdf](https://www.ti.com/lit/ds/symlink/sn74hc11.pdf) |
| 74HCT11 | Triple 3-input AND | HCT | 2 V | DIP14 | [cd74hct11.pdf](https://www.ti.com/lit/ds/symlink/cd74hct11.pdf) |
| 74HC14 | Hex Schmitt-trigger inverter | HC | 3.15 V | DIP14 | [sn74hc14.pdf](https://www.ti.com/lit/ds/symlink/sn74hc14.pdf) |
| 74HCT14 | Hex Schmitt-trigger inverter | HCT | 2 V | DIP14 | [sn74hct14.pdf](https://www.ti.com/lit/ds/symlink/sn74hct14.pdf) |
| 74HC20 | Dual 4-input NAND | HC | 3.15 V | DIP14 | [sn74hc20.pdf](https://www.ti.com/lit/ds/symlink/sn74hc20.pdf) |
| 74HCT20 | Dual 4-input NAND | HCT | 2 V | DIP14 | [cd74hct20.pdf](https://www.ti.com/lit/ds/symlink/cd74hct20.pdf) |
| 74HC21 | Dual 4-input AND | HC | 3.15 V | DIP14 | [sn74hc21.pdf](https://www.ti.com/lit/ds/symlink/sn74hc21.pdf) |
| 74HCT21 | Dual 4-input AND | HCT | 2 V | DIP14 | [cd74hct21.pdf](https://www.ti.com/lit/ds/symlink/cd74hct21.pdf) |
| 74HC27 | Triple 3-input NOR | HC | 3.15 V | DIP14 | [sn74hc27.pdf](https://www.ti.com/lit/ds/symlink/sn74hc27.pdf) |
| 74HCT27 | Triple 3-input NOR | HCT | 2 V | DIP14 | [cd74hct27.pdf](https://www.ti.com/lit/ds/symlink/cd74hct27.pdf) |
| 74HC30 | 8-input NAND | HC | 3.15 V | DIP14 | [cd74hc30.pdf](https://www.ti.com/lit/ds/symlink/cd74hc30.pdf) |
| 74HCT30 | 8-input NAND | HCT | 2 V | DIP14 | [cd74hct30.pdf](https://www.ti.com/lit/ds/symlink/cd74hct30.pdf) |
| 74HC32 | Quad 2-input OR | HC | 3.15 V | DIP14 | [sn74hc32.pdf](https://www.ti.com/lit/ds/symlink/sn74hc32.pdf) |
| 74HCT32 | Quad 2-input OR | HCT | 2 V | DIP14 | [sn74hct32.pdf](https://www.ti.com/lit/ds/symlink/sn74hct32.pdf) |
| 74HC74 | Dual D flip-flop, rising edge, active-low preset and clear | HC | 3.15 V | DIP14 | [sn74hc74.pdf](https://www.ti.com/lit/ds/symlink/sn74hc74.pdf) |
| 74HCT74 | Dual D flip-flop, rising edge, active-low preset and clear | HCT | 2 V | DIP14 | [sn74hct74.pdf](https://www.ti.com/lit/ds/symlink/sn74hct74.pdf) |
| 74HC86 | Quad 2-input XOR | HC | 3.15 V | DIP14 | [sn74hc86.pdf](https://www.ti.com/lit/ds/symlink/sn74hc86.pdf) |
| 74HCT86 | Quad 2-input XOR | HCT | 2 V | DIP14 | [cd74hct86.pdf](https://www.ti.com/lit/ds/symlink/cd74hct86.pdf) |
| 74HC107 | Dual JK flip-flop, negative-edge clock, async clear | HC | 3.15 V | DIP14 | [cd74hc107.pdf](https://www.ti.com/lit/ds/symlink/cd74hc107.pdf) |
| 74HCT107 | Dual JK flip-flop, negative-edge clock, async clear | HCT | 2 V | DIP14 | [cd74hct107.pdf](https://www.ti.com/lit/ds/symlink/cd74hct107.pdf) |
| 74HC109 | Dual J-K(bar) flip-flop, rising edge, active-low preset and clear | HC | 3.15 V | DIP16 | [cd74hc109.pdf](https://www.ti.com/lit/ds/symlink/cd74hc109.pdf) |
| 74HCT109 | Dual J-K(bar) flip-flop, rising edge, active-low preset and clear | HCT | 2 V | DIP16 | [cd74hct109.pdf](https://www.ti.com/lit/ds/symlink/cd74hct109.pdf) |
| 74HC112 | Dual J-K flip-flop, falling edge, active-low preset and clear | HC | 3.15 V | DIP16 | [cd74hc112.pdf](https://www.ti.com/lit/ds/symlink/cd74hc112.pdf) |
| 74HCT112 | Dual J-K flip-flop, falling edge, active-low preset and clear | HCT | 2 V | DIP16 | [cd74hct112.pdf](https://www.ti.com/lit/ds/symlink/cd74hct112.pdf) |
| 74HC125 | Quad tri-state buffer, active-low enables | HC | 3.15 V | DIP14 | [sn74hc125.pdf](https://www.ti.com/lit/ds/symlink/sn74hc125.pdf) |
| 74HCT125 | Quad tri-state buffer, active-low enables | HCT | 2 V | DIP14 | [sn74hct125.pdf](https://www.ti.com/lit/ds/symlink/sn74hct125.pdf) |
| 74HC126 | Quad tri-state buffer, active-high enables | HC | 3.15 V | DIP14 | [sn74hc126.pdf](https://www.ti.com/lit/ds/symlink/sn74hc126.pdf) |
| 74HCT126 | Quad tri-state buffer, active-high enables | HCT | 2 V | DIP14 | [cd74hct126.pdf](https://www.ti.com/lit/ds/symlink/cd74hct126.pdf) |
| 74HC132 | Quad 2-input NAND, Schmitt-trigger inputs | HC | 3.15 V | DIP14 | [sn74hc132.pdf](https://www.ti.com/lit/ds/symlink/sn74hc132.pdf) |
| 74HCT132 | Quad 2-input NAND, Schmitt-trigger inputs | HCT | 2 V | DIP14 | [cd74hct132.pdf](https://www.ti.com/lit/ds/symlink/cd74hct132.pdf) |
| 74HC138 | 3-to-8 line decoder, active-low outputs | HC | 3.15 V | DIP16 | [sn74hc138.pdf](https://www.ti.com/lit/ds/symlink/sn74hc138.pdf) |
| 74HCT138 | 3-to-8 line decoder, active-low outputs | HCT | 2 V | DIP16 | [cd74hct138.pdf](https://www.ti.com/lit/ds/symlink/cd74hct138.pdf) |
| 74HC139 | Dual 2-to-4 line decoder, active-low outputs | HC | 3.15 V | DIP16 | [sn74hc139.pdf](https://www.ti.com/lit/ds/symlink/sn74hc139.pdf) |
| 74HCT139 | Dual 2-to-4 line decoder, active-low outputs | HCT | 2 V | DIP16 | [cd74hct139.pdf](https://www.ti.com/lit/ds/symlink/cd74hct139.pdf) |
| 74HC151 | 8-to-1 multiplexer with true (Y) and inverted (W) outputs, active-low strobe G | HC | 3.15 V | DIP16 | [sn74hc151.pdf](https://www.ti.com/lit/ds/symlink/sn74hc151.pdf) |
| 74HCT151 | 8-to-1 multiplexer with true (Y) and inverted (W) outputs, active-low strobe G | HCT | 2 V | DIP16 | [cd74hct151.pdf](https://www.ti.com/lit/ds/symlink/cd74hct151.pdf) |
| 74HC153 | Dual 4-to-1 multiplexer, common selects A/B, active-low strobes 1G/2G | HC | 3.15 V | DIP16 | [sn74hc153.pdf](https://www.ti.com/lit/ds/symlink/sn74hc153.pdf) |
| 74HCT153 | Dual 4-to-1 multiplexer, common selects A/B, active-low strobes 1G/2G | HCT | 2 V | DIP16 | [74HC_HCT153.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT153.pdf) |
| 74HC157 | Quad 2-to-1 multiplexer | HC | 3.15 V | DIP16 | [sn74hc157.pdf](https://www.ti.com/lit/ds/symlink/sn74hc157.pdf) |
| 74HCT157 | Quad 2-to-1 multiplexer | HCT | 2 V | DIP16 | [cd74hct157.pdf](https://www.ti.com/lit/ds/symlink/cd74hct157.pdf) |
| 74HC161 | 4-bit synchronous binary counter, async clear, sync load | HC | 3.15 V | DIP16 | [sn74hc161.pdf](https://www.ti.com/lit/ds/symlink/sn74hc161.pdf) |
| 74HCT161 | 4-bit synchronous binary counter, async clear, sync load | HCT | 2 V | DIP16 | [cd74hct161.pdf](https://www.ti.com/lit/ds/symlink/cd74hct161.pdf) |
| 74HC163 | 4-bit synchronous binary counter, synchronous reset and load | HC | 3.15 V | DIP16 | [74HC_HCT163.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT163.pdf) |
| 74HCT163 | 4-bit synchronous binary counter, synchronous reset and load | HCT | 2 V | DIP16 | [74HC_HCT163.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT163.pdf) |
| 74HC164 | 8-bit serial-in, parallel-out shift register, gated serial inputs, active-low reset | HC | 3.15 V | DIP14 | [74HC_HCT164.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT164.pdf) |
| 74HCT164 | 8-bit serial-in, parallel-out shift register, gated serial inputs, active-low reset | HCT | 2 V | DIP14 | [74HC_HCT164.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT164.pdf) |
| 74HC165 | 8-bit parallel-in, serial-out shift register, active-low asynchronous load PL, active-low clock enable CE (the clock is CP OR CE) | HC | 3.15 V | DIP16 | [74HC_HCT165.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT165.pdf) |
| 74HCT165 | 8-bit parallel-in, serial-out shift register, active-low asynchronous load PL, active-low clock enable CE (the clock is CP OR CE) | HCT | 2 V | DIP16 | [74HC_HCT165.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT165.pdf) |
| 74HC173 | 4-bit D register, tri-state outputs, async clear | HC | 3.15 V | DIP16 | [cd74hc173.pdf](https://www.ti.com/lit/ds/symlink/cd74hc173.pdf) |
| 74HCT173 | 4-bit D register, tri-state outputs, async clear | HCT | 2 V | DIP16 | [cd74hct173.pdf](https://www.ti.com/lit/ds/symlink/cd74hct173.pdf) |
| 74HC174 | Hex D flip-flop, async clear | HC | 3.15 V | DIP16 | [sn74hc174.pdf](https://www.ti.com/lit/ds/symlink/sn74hc174.pdf) |
| 74HCT174 | Hex D flip-flop, async clear | HCT | 2 V | DIP16 | [cd74hct174.pdf](https://www.ti.com/lit/ds/symlink/cd74hct174.pdf) |
| 74HC175 | Quad D flip-flop with Q and Q-bar outputs, active-low master reset | HC | 3.15 V | DIP16 | [74HC_HCT175.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT175.pdf) |
| 74HCT175 | Quad D flip-flop with Q and Q-bar outputs, active-low master reset | HCT | 2 V | DIP16 | [74HC_HCT175.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT175.pdf) |
| 74LS181 | 4-bit arithmetic logic unit / function generator (16 logic and 16 arithmetic functions) | LS | 2 V | DIP24 | [74LS181.pdf](https://mil.ufl.edu/4712/docs/74LS181.pdf) |
| 74HC191 | 4-bit synchronous up/down binary counter, asynchronous load | HC | 3.15 V | DIP16 | [cd74hc191.pdf](https://www.ti.com/lit/ds/symlink/cd74hc191.pdf) |
| 74HCT191 | 4-bit synchronous up/down binary counter, asynchronous load | HCT | 2 V | DIP16 | [cd74hct191.pdf](https://www.ti.com/lit/ds/symlink/cd74hct191.pdf) |
| 74HC193 | 4-bit synchronous up/down binary counter, dual clock, async reset and load | HC | 3.15 V | DIP16 | [74HC_HCT193.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT193.pdf) |
| 74HCT193 | 4-bit synchronous up/down binary counter, dual clock, async reset and load | HCT | 2 V | DIP16 | [74HC_HCT193.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT193.pdf) |
| 74HC240 | Octal inverting buffer/line driver, tri-state, active-low enables | HC | 3.15 V | DIP20 | [74HC_HCT240.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT240.pdf) |
| 74HCT240 | Octal inverting buffer/line driver, tri-state, active-low enables | HCT | 2 V | DIP20 | [74HC_HCT240.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT240.pdf) |
| 74HC241 | Octal buffer/line driver, tri-state, 1OE active low, 2OE active high | HC | 3.15 V | DIP20 | [74HC_HCT241.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT241.pdf) |
| 74HCT241 | Octal buffer/line driver, tri-state, 1OE active low, 2OE active high | HCT | 2 V | DIP20 | [74HC_HCT241.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT241.pdf) |
| 74HC244 | Octal buffer/line driver, tri-state, active-low enables | HC | 3.15 V | DIP20 | [74HC_HCT244.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT244.pdf) |
| 74HCT244 | Octal buffer/line driver, tri-state, active-low enables | HCT | 2 V | DIP20 | [74HC_HCT244.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT244.pdf) |
| 74HC245 | Octal bus transceiver, tri-state | HC | 3.15 V | DIP20 | [sn74hc245.pdf](https://www.ti.com/lit/ds/symlink/sn74hc245.pdf) |
| 74HCT245 | Octal bus transceiver, tri-state | HCT | 2 V | DIP20 | [cd74hct245.pdf](https://www.ti.com/lit/ds/symlink/cd74hct245.pdf) |
| 74HC273 | Octal D flip-flop, active-low master reset | HC | 3.15 V | DIP20 | [74HC_HCT273.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT273.pdf) |
| 74HCT273 | Octal D flip-flop, active-low master reset | HCT | 2 V | DIP20 | [74HC_HCT273.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT273.pdf) |
| 74HC283 | 4-bit binary full adder with fast carry | HC | 3.15 V | DIP16 | [cd74hc283.pdf](https://www.ti.com/lit/ds/symlink/cd74hc283.pdf) |
| 74HCT283 | 4-bit binary full adder with fast carry | HCT | 2 V | DIP16 | [cd74hct283.pdf](https://www.ti.com/lit/ds/symlink/cd74hct283.pdf) |
| 74HC373 | Octal transparent D latch, tri-state outputs (active-low OE) | HC | 3.15 V | DIP20 | [74HC_HCT373.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT373.pdf) |
| 74HCT373 | Octal transparent D latch, tri-state outputs (active-low OE) | HCT | 2 V | DIP20 | [74HC_HCT373.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT373.pdf) |
| 74HC374 | Octal D flip-flop, rising edge, tri-state outputs (active-low OE) | HC | 3.15 V | DIP20 | [74HC_HCT374.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT374.pdf) |
| 74HCT374 | Octal D flip-flop, rising edge, tri-state outputs (active-low OE) | HCT | 2 V | DIP20 | [74HC_HCT374.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT374.pdf) |
| 74HC377 | Octal D flip-flop with clock enable | HC | 3.15 V | DIP20 | [cd74hc377.pdf](https://www.ti.com/lit/ds/symlink/cd74hc377.pdf) |
| 74HCT377 | Octal D flip-flop with clock enable | HCT | 2 V | DIP20 | [cd74hct377.pdf](https://www.ti.com/lit/ds/symlink/cd74hct377.pdf) |
| 74HC541 | Octal buffer/line driver, tri-state, two active-low enables, flow-through pin-out | HC | 3.15 V | DIP20 | [74HC_HCT541.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT541.pdf) |
| 74HCT541 | Octal buffer/line driver, tri-state, two active-low enables, flow-through pin-out | HCT | 2 V | DIP20 | [74HC_HCT541.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT541.pdf) |
| 74HC573 | Octal transparent D latch, tri-state outputs (active-low OE), flow-through pin-out | HC | 3.15 V | DIP20 | [74HC_HCT573.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT573.pdf) |
| 74HCT573 | Octal transparent D latch, tri-state outputs (active-low OE), flow-through pin-out | HCT | 2 V | DIP20 | [74HC_HCT573.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT573.pdf) |
| 74HC574 | Octal D flip-flop, rising edge, tri-state outputs (active-low OE), flow-through pin-out | HC | 3.15 V | DIP20 | [74HC_HCT574.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT574.pdf) |
| 74HCT574 | Octal D flip-flop, rising edge, tri-state outputs (active-low OE), flow-through pin-out | HCT | 2 V | DIP20 | [74HC_HCT574.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT574.pdf) |
| 74HC595 | 8-bit shift register with output latch | HC | 3.15 V | DIP16 | [sn74hc595.pdf](https://www.ti.com/lit/ds/symlink/sn74hc595.pdf) |
| 74HCT595 | 8-bit shift register with output latch | HCT | 2 V | DIP16 | [sn74hct595.pdf](https://www.ti.com/lit/ds/symlink/sn74hct595.pdf) |
| 74HC4040 | 12-stage binary ripple counter, falling-edge clock, active-high reset | HC | 3.15 V | DIP16 | [74HC_HCT4040.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT4040.pdf) |
| 74HCT4040 | 12-stage binary ripple counter, falling-edge clock, active-high reset | HCT | 2 V | DIP16 | [74HC_HCT4040.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT4040.pdf) |
| 74HC4060 | 14-stage binary ripple counter with oscillator pins, falling-edge clock on RS, active-high reset (RTC/CTC are the analogue oscillator pins, not simulated: drive RS from a clock) | HC | 3.15 V | DIP16 | [74HC_HCT4060.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT4060.pdf) |
| 74HCT4060 | 14-stage binary ripple counter with oscillator pins, falling-edge clock on RS, active-high reset (RTC/CTC are the analogue oscillator pins, not simulated: drive RS from a clock) | HCT | 2 V | DIP16 | [74HC_HCT4060.pdf](https://assets.nexperia.com/documents/data-sheet/74HC_HCT4060.pdf) |
| 6116 | 2K x 8 static RAM | memory | 2 V | DIP24 | [6116sala-data-sheet](https://www.renesas.com/us/en/document/dst/6116sala-data-sheet) |
| NE555 | Timer (astable, monostable or bistable) | timer | — | DIP8 | [ne555.pdf](https://www.ti.com/lit/ds/symlink/ne555.pdf) |
| AT28C16 | 2K x 8 parallel EEPROM (programmed outside the circuit) | memory | 2 V | DIP24 | [ATMEL-AT28C16E15SC.pdf](https://ipv4.pccomponents.com/datasheets/ATMEL-AT28C16E15SC.pdf) |
| AT28C256 | 32K x 8 parallel EEPROM | memory | 2 V | DIP28 | [index.html](https://onlinedocs.microchip.com/oxy/GUID-7B73D324-9159-4988-92D8-6062218CD25C-en-US-2/index.html) |
| AS6C62256 | 32K x 8 static RAM | memory | 2.2 V | DIP28 | [AS6C62256-23-March-2016-rev1.2.pdf](https://www.alliancememory.com/wp-content/uploads/AS6C62256-23-March-2016-rev1.2.pdf) |
