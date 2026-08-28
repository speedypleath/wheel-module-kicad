# Stripboard wiring guide — Wheel Module (M3) encoder sensor board

Build reference for `project/haptic-console-wheel-module-stripboard.kicad_pcb`.
Generated from the placed board on 2026-08-28. Circuit itself is in `README.md`.

This is the **Veroboard** build. It is a different board from
`docs/perfboard-wiring.md`, which covers the point-to-point plain-perfboard build.
Pick one; they are not interchangeable.

## Grid convention

Continuous-strip Veroboard, **28 columns × 30 rows** on 2.54 mm, cut to
**73.66 × 78.74 mm**. Copper strips run **horizontally**, one per row, the full
width of the board.

```
x = col * 2.54 mm        col 1..28, left to right
y = row * 2.54 mm        row 1..30, top to bottom
```

`(1,1)` is the top-left hole, with one clear 2.54 mm margin on every edge. All
column/row references below are given **component side, Pico USB at the top** —
matching `renders/stripboard-top.png`. Remember the copper is on the **back**, so
when you flip the board to cut, columns mirror.

## Read this first: the strip is shared by every hole in its row

On plain perfboard a hole connects to nothing. Here it connects to the whole row.
So a pin you never wired still shorts to whatever else sits on its strip. Two
consequences drove this entire layout:

- **Row 10 must be cut at column 12.** Pico pin 8 (GND) is on the left of that
  row and pin 33 (**AGND**) is on the right. AGND is a deliberate no-connect —
  tying it to GND re-creates the `power_out`/`power_out` ERC violation documented
  in `CLAUDE.md`. Leave that cut out and you have broken a design invariant.
- **Rows 5, 15 and 20 are deliberately NOT cut.** Those three rows carry GND on
  *both* sides of the Pico (pins 3/38, 13/28, 18/23), so leaving them whole gives
  six GND connections for free and forms the GND bus.

## Cuts — 23 of them

Cut with a spot-face cutter or a 3 mm drill twisted by hand, **at the hole**,
from the copper side. Each cut removes the copper around one hole; that hole is
then dead. Marked with an `X` on the back silkscreen in the render.

| Column | Rows | Why |
|---|---|---|
| **12** | 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 21, 22 | Splits the Pico's left pins from its right pins. **Not** 5/15/20 — those stay whole as the GND bus. |
| **12** | 26 | Separates `Net-(D1-A)` (left) from `+5V` (right). |
| **5** | 6, 7, 10 | Isolates `J1` pins 2, 3 and 6, whose order disagrees with the Pico's. |
| **26** | 22 | Isolates `J2.5` (shield GND) from `/ENC_A`. |
| **27** | 25 | Isolates `J2.2` (GND) from `+3V3`. |

Count them before soldering anything. A missed cut on row 10 or row 12 is the
expensive kind.

## Strip allocation

Every strip segment carries exactly one net — verified against the saved board,
not against intent.

| Row | Columns | Net | Pads on it |
|---|---|---|---|
| 1 | all | *(spare)* | — |
| 2 | all | `+5V` | rail, fed by link wires only |
| 3 | 1–11 / 13–28 | *(unused Pico pins)* | U1.1 / U1.40 |
| 4 | 13–28 | `+5V` | U1.39, C1.1 |
| **5** | **all (uncut)** | `GND` | U1.3, U1.38, J1.1, C1.2 |
| 6 | 1–4 | *(no-connect)* | **J1.2 — hub 3.3V, must stay isolated** |
| 6 | 6–11 | `/LNK` | U1.4 |
| 7 | 1–4 | `+5V` | J1.3 |
| 7 | 13–28 | `+3V3` | U1.36 |
| 8 | 1–11 | `/SDA` | U1.6, J1.4 |
| 9 | 1–11 | `/SCL` | U1.7, J1.5 |
| 10 | 1–4 | `/IRQ` | J1.6 |
| 10 | 6–11 | `GND` | U1.8 |
| 10 | 13–28 | *(no-connect)* | **U1.33 AGND — must stay isolated** |
| 11 | 1–11 | `/IRQ` | U1.9 |
| 12–14, 16–19 | — | *(unused Pico pins)* | one per side, bare |
| **15** | **all (uncut)** | `GND` | U1.13, U1.28 |
| **20** | **all (uncut)** | `GND` | U1.18, U1.23 |
| 21 | 13–28 | `/ENC_B` | U1.22, R5.1 |
| 22 | 13–25 | `/ENC_A` | U1.21, R4.1 |
| 22 | 27–28 | `GND` | J2.5 |
| 23 | all | `/ENC_B_RAW` | R5.2, R2.2, J2.4 |
| 24 | all | `/ENC_A_RAW` | R4.2, R1.2, J2.3 |
| 25 | 1–26 | `+3V3` | R7.1, R2.1, R1.1, C2.1 |
| 25 | 28 | `GND` | J2.2 |
| 26 | 1–11 | `Net-(D1-A)` | R7.2, D1.2 |
| 26 | 13–28 | `+5V` | J2.1 |
| 27 | all | `GND` | D1.1, D2.1, C2.2 |
| 28 | all | `Net-(D2-A)` | D2.2, R8.2 |
| 29 | all | `/LNK` | R8.1 |
| 30 | all | *(spare)* | — |

## Placement

Pad 1 sits at the stated hole for every part. **All six resistors stand on end**
— this is the Veroboard idiom and it is what stops them shorting along a strip.

| Ref | Value | Footprint | Pad 1 | Occupies |
|---|---|---|---|---|
| U1 | Pico | `RaspberryPi_Pico_Common_THT` | (9,3) | cols 9 & 16, rows 3–22 |
| J1 | XH2.54 6-pin | `JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical` | (2,5) | col 2, rows 5–10 |
| J2 | 5-pin header | `PinHeader_1x05_P2.54mm_Vertical` | (28,26) | col 28, rows 22–26, **pin 1 at the bottom** |
| R1 | 4.7k | `R_Axial_..._P2.54mm_Vertical` | (24,25) | col 24, rows 24–25 |
| R2 | 4.7k | `R_Axial_..._P5.08mm_Vertical` | (22,25) | col 22, rows 23–25 |
| R4 | 220R | `R_Axial_..._P5.08mm_Vertical` | (20,22) | col 20, rows 22–24 |
| R5 | 220R | `R_Axial_..._P5.08mm_Vertical` | (18,21) | col 18, rows 21–23 |
| R7 | 1k | `R_Axial_..._P2.54mm_Vertical` | (2,25) | col 2, rows 25–26 |
| R8 | 1k | `R_Axial_..._P2.54mm_Vertical` | (2,29) | col 2, rows 28–29 |
| C1 | 10uF | `C_Disc_D5.0mm_W2.5mm_P2.50mm` | (18,4) | col 18, rows 4–5 |
| C2 | 100nF | `C_Disc_D5.0mm_W2.5mm_P5.00mm` | (26,25) | col 26, rows 25–27 |
| D1 | power LED | `LED_D3.0mm` | (4,27) | col 4, rows 26–27, pad 1 = cathode = GND |
| D2 | link LED | `LED_D3.0mm` | (6,27) | col 6, rows 27–28, pad 1 = cathode = GND |

Two parts are very slightly off-grid and this is fine — the leads bend:

- `J1` is a 2.50 mm connector on a 2.54 mm grid: pin 6 lands 0.2 mm above row 10,
  cumulative over six pins. XH pins are 0.6 mm in 1.0 mm holes.
- `C1` (2.50 mm) and `C2` (5.00 mm) are 0.04 mm and 0.08 mm out respectively.

`R4` and `R5` are the nicest part of this layout: they reach straight from the
Pico's `/ENC_A`/`/ENC_B` pins down to the `_RAW` rows with **no link wire at
all**, so the two noise-sensitive nets are pure copper.

## Link wires — 9 of them

**Insulated wire on the solder side**, hole to hole. The component side is
crowded — the Pico spans twenty rows and `J1`, `J2` and the LEDs sit on the very
edges the long links follow — so wires there would lie across component bodies.
The back is flat: insulated wire over a copper strip touches nothing.

Colours follow the console convention, shared with the control unit so the same
net is the same colour on every board: **red** for power (`+5V` and `+3V3` both —
the kit has six colours and consistency across boards wins over telling the two
rails apart at a glance), **blue** for GND (the kit has no black), **yellow** for
the I²C/IRQ bus, **green** for `/LNK`.

| # | Net | Colour | From | To | Purpose |
|---|---|---|---|---|---|
| 1 | `+5V` | red | (2,7) `J1.3` | (2,2) | console 5V up to the rail |
| 2 | `/IRQ` | yellow | (2,10) `J1.6` | (4,11) | J1's IRQ pin down to the Pico's |
| 3 | `+5V` | red | (19,4) | (19,2) | Pico VSYS to the rail |
| 4 | `+5V` | red | (27,2) | (28,26) `J2.1` | rail down to the encoder connector |
| 5 | `+3V3` | red | (18,7) | (18,25) | Pico 3V3 out to the pull-up rail |
| 6 | `/LNK` | green | (6,6) | (6,29) | Pico GP2 down to the LED resistor |
| 7 | `GND` | blue | (7,5) | (7,27) | GND spine — **solder it also at rows 10, 15 and 20 on the way past** |
| 8 | `GND` | blue | (27,22) | (27,27) | `J2.5` cable shield to GND |
| 9 | `GND` | blue | (28,25) | (28,27) | `J2.2` encoder GND to GND |

Wire 7 is one length soldered at five holes — rows 5, 10, 15, 20 and 27. Those
three intermediate joints are what tie the Pico's GND rows into one bus; skipping
any of them leaves that row floating. (The board file models them as three extra
zero-length links, which is why the netlist counts twelve and this table nine.)

Wire 9 passes directly over `J2` pin 1, where wire 4 lands. Both are insulated —
let 9 lie over 4 rather than trying to dodge it.

## Build order

1. **Make all 23 cuts first**, before any part goes in. Check each one for
   continuity across the gap — a partial cut is the hardest fault to find later.
2. **Fit the Pico on female headers**, not soldered down. Two GND strips and the
   whole cut column run underneath it.
3. **Resistors, LEDs, caps.** All resistors vertical. Watch LED polarity: pad 1
   is the cathode and goes to the GND row (27) for both.
4. **`J1` and `J2`.**
5. **Link wires last.** They go on the *solder* side, so they follow the parts
   rather than preceding them: each end lands in the named hole and is soldered
   to that strip alongside the component lead already there. Strip and tin both
   ends first — a wire soldered onto an already-crowded joint is the easiest one
   to lift by accident.
6. Before power-up, check with a meter: `+5V` to `GND` open, `+3V3` to `GND`
   open, and **`U1.33` (AGND) isolated from GND** — that last one is the specific
   thing this layout's row-10 cut exists to guarantee.

## Verification state

- `kicad-cli pcb drc`: **0 errors, 0 unconnected pads, 0 footprint errors.**
- Strip audit (`every segment carries exactly one net`): **clean**, including the
  two isolation invariants above.
- 240 DRC *warnings* remain, all `via_dangling`/`track_dangling` plus three
  pre-existing `lib_footprint_mismatch`. These are expected — see `CLAUDE.md`.
