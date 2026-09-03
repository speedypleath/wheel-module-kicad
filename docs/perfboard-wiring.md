# Perfboard wiring guide — Wheel Module (M3) encoder sensor board

Hand-wiring reference for `project/haptic-console-wheel-module-perfboard.kicad_pcb`.
Generated from the placed board on 2026-08-28. Circuit itself is in `README.md`.

## Grid convention

Plain 2.54 mm perfboard, cut to **71.12 × 71.12 mm** (28 × 28 holes).

A hole is addressed as **(col, row)**, both 1-based from the top-left corner:

```
x = col * 2.54 mm        col 1..28, left to right
y = row * 2.54 mm        row 1..28, top to bottom
```

So (1,1) is the top-left hole and there is one clear 2.54 mm margin on every edge.
This matches the orientation of `renders/perfboard-top.png` — view from the
**component side**, Pico USB connector at the top.

## Placement summary

| Ref | Occupies | Notes |
|---|---|---|
| U1 Pico | cols 9 and 16, rows 4–23 | pin 1 at (9,4); left pin row descends, right pin row ascends |
| J1 console XH6 | col 2, rows 6–11 | pin 1 (GND) at top |
| J2 encoder 1x05 | col 25, rows 20–24 | **pin 1 at the bottom** (row 24), footprint is rotated 180° |
| R1, R2 | rows 26 and 19 | 4.7k pull-ups to +3V3 |
| R4, R5 | rows 23 and 21 | 330R series protection |
| R7, R8 | rows 15 and 13, cols 3–7 | 1k LED limiters, rotated 180° |
| D1, D2 | cols 1–2, rows 15 and 13 | pad 1 = cathode = GND |
| C1, C2 | C1 cols 18–19 row 5, C2 cols 18–20 row 8 | bulk (polarised) and decoupling |

Resistors sit two rows apart so the axial bodies never touch.

**C1 is polarised** — a 10 µF 25 V D4x7 electrolytic. Pad 1 is **+** and goes to (18,5)
on `+5V`; the striped **−** lead goes to (19,5) on `GND`. It spans two holes rather
than three because the electrolytic's leads are 2.5 mm apart, not 5 mm.

## Nets

| Net | Pads (col,row) |
|---|---|
| `+3V3` | **U1.36** (16,8) — **C2.1** (18,8) — **R7.1** (7,15) — **R2.1** (19,19) — **R1.1** (18,26) |
| `+5V` | **U1.39** (16,5) — **C1.1** (18,5) — **J1.3** (2,8) — **J2.1** (25,24) |
| `/ENC_A` | **U1.21** (16,23) — **R4.1** (18,23) |
| `/ENC_A_RAW` | **J2.3** (25,22) — **R4.2** (22,23) — **R1.2** (22,26) |
| `/ENC_B` | **R5.1** (18,21) — **U1.22** (16,22) |
| `/ENC_B_RAW` | **R2.2** (23,19) — **R5.2** (22,21) — **J2.4** (25,21) |
| `/IRQ` | **J1.6** (2,11) — **U1.9** (9,12) |
| `/LNK` | **U1.4** (9,7) — **R8.1** (7,13) |
| `/SCL` | **J1.5** (2,10) — **U1.7** (9,10) |
| `/SDA` | **J1.4** (2,9) — **U1.6** (9,9) |
| `GND` | **C1.2** (19,5) — **J1.1** (2,6) — **U1.3** (9,6) — **U1.38** (16,6) — **C2.2** (20,8) — **U1.8** (9,11) — **D2.1** (1,13) — **D1.1** (1,15) — **U1.13** (9,16) — **U1.28** (16,16) — **J2.5** (25,20) — **U1.18** (9,21) — **U1.23** (16,21) — **J2.2** (25,23) |
| `Net-(D1-A)` | **D1.2** (2,15) — **R7.2** (3,15) |
| `Net-(D2-A)` | **D2.2** (2,13) — **R8.2** (3,13) |

## Wiring notes, in build order

Solder in this order — shortest and most constrained runs first, so nothing is
trapped underneath a part you cannot reach later.

**1. Sockets and connectors first.** Fit the Pico on female headers rather than
soldering it down. Two of the runs below pass under it and you will want the
option of lifting it off.

**2. The free same-row runs.** These need one straight wire each, no jogs:

- `/SDA` — J1.4 (2,9) to U1.6 (9,9)
- `/SCL` — J1.5 (2,10) to U1.7 (9,10)
- `/ENC_A` — U1.21 (16,23) to R4.1 (18,23)
- `+5V` local — U1.39 (16,5) to C1.1 (18,5)
- `+3V3` local — U1.36 (16,8) to C2.1 (18,8)

**3. The one-hole jogs.** `/IRQ` J1.6 (2,11) to U1.9 (9,12), and `/ENC_B`
U1.22 (16,22) to R5.1 (18,21). The connector and Pico pin orders run opposite
ways here; one row of diagonal absorbs it.

**4. Encoder signal pairs.** Keep these short — they are the only nodes on the
board where edge quality matters:

- `/ENC_A_RAW` — R4.2 (22,23) up column 22 to R1.2 (22,26), then across to J2.3 (25,22)
- `/ENC_B_RAW` — R5.2 (22,21) across row 21 to J2.4 (25,21), and diagonally to R2.2 (23,19)

Column 22 carries `/ENC_A_RAW` on rows 23–26 and `/ENC_B_RAW` only at row 21, so
the two never share a segment. Do not let them.

**5. Rails last.** GND has 14 nodes and +3V3 has 5. Bus them along a shared row
or column rather than home-running each one.

## Two long runs, called out deliberately

**`+3V3` to R7.1 (7,15) crosses the Pico.** Everything else on +3V3 lives on the
right-hand side (cols 16–19); the PWR LED's resistor is on the left. Either run
this wire underneath the Pico before seating it, or take it the long way round
via row 25. Decide before step 1 — under the Pico is tidier but only reachable
while the module is off its socket.

**`+5V` from J1.3 (2,8) to U1.39 (16,5)** crosses the full board width. This is
unavoidable: the Pico's VSYS is pin 39 on the right-hand side while the console
connector has to be on the left, next to I2C. The trade was deliberate — SDA,
SCL and IRQ are the signal-integrity-sensitive nets and they got the short runs,
while +5V is a power rail with C1 bulk decoupling sitting directly at the Pico
pin. Route it along the top edge (row 2–3) rather than through the middle.

## Gotchas

- **J1 is 2.5 mm pitch on a 2.54 mm grid.** Over six pins that accumulates
  0.2 mm. It seats fine — this was already confirmed on the control-unit
  perfboard — but ease it in rather than forcing it.
- **J2 is rotated 180°**, so encoder pin 1 (red, V+) is the *bottom* hole at
  (25,24) and the shield is the *top* hole at (25,20). Easy to wire backwards.
- **D1/D2 pad 1 is the cathode** and goes to GND. Check the flat before soldering.
- **Encoder runs from the console 5V rail.** The 12V option is deliberately not
  built — see `README.md`.

## Verification

```bash
export KICAD_SYMBOL_DIR=/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols
export KICAD_FOOTPRINT_DIR=/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints
kicad-cli pcb drc --format report project/haptic-console-wheel-module-perfboard.kicad_pcb -o docs/drc-perfboard.txt
kicad-cli pcb render --side top --width 1400 --height 1400 -o renders/perfboard-top.png project/haptic-console-wheel-module-perfboard.kicad_pcb
```

Current state: **0 DRC errors, 9 warnings.** The warnings are five
`lib_footprint_mismatch` (tool-placed footprint copies differing cosmetically
from the library), three `silk_overlap` on D2's reference text under J1's
outline, and one `silk_over_copper` on U1's reference. All cosmetic.

The 32 "unconnected pads" DRC reports are **expected and correct** — this board
has no copper traces by design. Connectivity lives in the wire list above.

## Full pad reference


| Ref | Pad | Col | Row | Net |
|---|---|---|---|---|
| C1 | 1 | 18 | 5 | `+5V` |
| C1 | 2 | 19 | 5 | `GND` |
| C2 | 1 | 18 | 8 | `+3V3` |
| C2 | 2 | 20 | 8 | `GND` |
| D1 | 1 | 1 | 15 | `GND` |
| D1 | 2 | 2 | 15 | `Net-(D1-A)` |
| D2 | 1 | 1 | 13 | `GND` |
| D2 | 2 | 2 | 13 | `Net-(D2-A)` |
| J1 | 1 | 2 | 6 | `GND` |
| J1 | 3 | 2 | 8 | `+5V` |
| J1 | 4 | 2 | 9 | `/SDA` |
| J1 | 5 | 2 | 10 | `/SCL` |
| J1 | 6 | 2 | 11 | `/IRQ` |
| J2 | 1 | 25 | 24 | `+5V` |
| J2 | 2 | 25 | 23 | `GND` |
| J2 | 3 | 25 | 22 | `/ENC_A_RAW` |
| J2 | 4 | 25 | 21 | `/ENC_B_RAW` |
| J2 | 5 | 25 | 20 | `GND` |
| R1 | 1 | 18 | 26 | `+3V3` |
| R1 | 2 | 22 | 26 | `/ENC_A_RAW` |
| R2 | 1 | 19 | 19 | `+3V3` |
| R2 | 2 | 23 | 19 | `/ENC_B_RAW` |
| R4 | 1 | 18 | 23 | `/ENC_A` |
| R4 | 2 | 22 | 23 | `/ENC_A_RAW` |
| R5 | 1 | 18 | 21 | `/ENC_B` |
| R5 | 2 | 22 | 21 | `/ENC_B_RAW` |
| R7 | 1 | 7 | 15 | `+3V3` |
| R7 | 2 | 3 | 15 | `Net-(D1-A)` |
| R8 | 1 | 7 | 13 | `/LNK` |
| R8 | 2 | 3 | 13 | `Net-(D2-A)` |
| U1 | 3 | 9 | 6 | `GND` |
| U1 | 4 | 9 | 7 | `/LNK` |
| U1 | 6 | 9 | 9 | `/SDA` |
| U1 | 7 | 9 | 10 | `/SCL` |
| U1 | 8 | 9 | 11 | `GND` |
| U1 | 9 | 9 | 12 | `/IRQ` |
| U1 | 13 | 9 | 16 | `GND` |
| U1 | 18 | 9 | 21 | `GND` |
| U1 | 21 | 16 | 23 | `/ENC_A` |
| U1 | 22 | 16 | 22 | `/ENC_B` |
| U1 | 23 | 16 | 21 | `GND` |
| U1 | 28 | 16 | 16 | `GND` |
| U1 | 36 | 16 | 8 | `+3V3` |
| U1 | 38 | 16 | 6 | `GND` |
| U1 | 39 | 16 | 5 | `+5V` |
