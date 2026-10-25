from pc2_netlist import build
import layout
N=build()
boards,links=layout.layout(N)
for name in layout.BOARD_ORDER:
    B=boards[name]
    print(f"{name:<22} rows used {B.next-1:>3}  wires {len(B.wires):>3}  overflow {B.overflow[:3]}")
print('board-to-board wires', len(links))
p=layout.check(N,boards,links)
print('check problems', len(p)); print(p[:15])
