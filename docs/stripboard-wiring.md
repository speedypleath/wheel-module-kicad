# Stripboard wiring guide — Wheel Module (M3) encoder sensor board

Build reference for `project/haptic-console-wheel-module-stripboard.kicad_pcb`.
Generated from the placed board; grid resized to the real 40 x 40 stock on
2026-08-30. Circuit itself is in `README.md`.

There is an interactive version of this document at
[`docs/stripboard-wiring.html`](stripboard-wiring.html) — same content, plus a
board map, a searchable cut list and a tickable solder checklist. Open it in a
browser; it is a single self-contained file.

This is the **Veroboard** build. It is a different board from
`docs/perfboard-wiring.md`, which covers the point-to-point plain-perfboard build.
Pick one; they are not interchangeable.

## Grid convention

Continuous-strip Veroboard, **40 columns × 40 rows** on 2.54 mm — a full
**104.14 mm square** board, uncut. Copper strips run **horizontally**, one per
row, the full width of the board.

```
x = col * 2.54 mm        col 1..40, left to right
y = row * 2.54 mm        row 1..40, top to bottom
```

The circuit occupies **cols 1–28, rows 1–28**, in the top-left corner. Everything
right of column 28 and below row 28 is spare board. That spare copper is not
inert: each strip still runs the full 40 columns, so the right-hand end of a row
is electrically the same node as the part of it the circuit uses. Treat it as
free tie points, and keep it clear of stray solder bridges between rows.

`(1,1)` is the top-left hole, with one clear 2.54 mm margin on every edge. All
column/row references below are given **component side, Pico USB at the top** —
matching `renders/stripboard-top.png`. Remember the copper is on the **back**, so
when you flip the board to cut, columns mirror.

**Row 1 carries nothing.** The Pico's body is 51 mm long but spans only 19 pin
pitches (48.26 mm), so it overhangs its end rows by 1.37 mm: the body edge sits
at y = 3.71 mm while a row-1 hole's copper ends at 3.29 mm. That is 0.42 mm of
daylight — real, but not worth soldering into. The USB shell overhangs a further
1.3 mm on top of that, though it rides 8.5 mm up in the air on the socket
headers and fouls nothing.

## Read this first: the strip is shared by every hole in its row

On plain perfboard a hole connects to nothing. Here it connects to the whole row.
So a pin you never wired still shorts to whatever else sits on its strip. Two
consequences drove this entire layout:

- **Row 9 must be cut at column 12.** Pico pin 8 (GND) is on the left of that
  row and pin 33 (**AGND**) is on the right. AGND is a deliberate no-connect —
  tying it to GND re-creates the `power_out`/`power_out` ERC violation documented
  in `CLAUDE.md`. Leave that cut out and you have broken a design invariant.
- **Rows 4, 14 and 19 are deliberately NOT cut.** Those three rows carry GND on
  *both* sides of the Pico (pins 3/38, 13/28, 18/23), so leaving them whole gives
  six GND connections for free and forms the GND bus.

### And why `+5V` has no strip of its own

A strip that spans the Pico is only safe on a row whose two pins are the same
net, and the only such rows are the three GND ones. So `+5V` cannot have a
full-width rail. It lives on **row 3's right-hand segment**, where the Pico's
own VSYS pin and `C1` already sit, and the hub's 5 V — which arrives on the far
left at `J1.3` — is carried over the top of the module to reach it (wire 1).
Row 3's *left* segment must stay cut off at column 12: it carries Pico pin 2,
GPIO1, and 5 V on a GPIO would destroy the chip.

## Cuts — 23 of them

Cut with a spot-face cutter or a 3 mm drill twisted by hand, **at the hole**,
from the copper side. Each cut removes the copper around one hole; that hole is
then dead. Marked with an `X` on the back silkscreen in the render.

| Column | Rows | Why |
|---|---|---|
| **12** | 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 20, 21 | Splits the Pico's left pins from its right pins. **Not** 4/14/19 — those stay whole as the GND bus. |
| **12** | 25 | Separates `Net-(D1-A)` (left) from `+5V` (right). |
| **5** | 5, 6, 9 | Isolates `J1` pins 2, 3 and 6, whose order disagrees with the Pico's. |
| **26** | 21 | Isolates `J2.5` (shield GND) from `/ENC_A`. |
| **27** | 24 | Isolates `J2.2` (GND) from `+3V3`. |

Count them before soldering anything. A missed cut on row 9 or row 3 is the
expensive kind.

## Strip allocation

Every strip segment carries exactly one net — verified against the saved board,
not against intent.

| Row | Columns | Net | Pads on it |
|---|---|---|---|
| 1 | all | *(spare — under the module overhang)* | — |
| 2 | 1–11 / 13–40 | *(unused Pico pins)* | U1.1 / U1.40 |
| 3 | 1–11 | *(unused)* | U1.2 |
| 3 | 13–40 | `+5V` | U1.39, C1.1 |
| **4** | **all (uncut)** | `GND` | U1.3, U1.38, J1.1, C1.2 |
| 5 | 1–4 | *(no-connect)* | **J1.2 — hub 3.3V, must stay isolated** |
| 5 | 6–11 | `/LNK` | U1.4 |
| 5 | 13–40 | *(unused)* | U1.37 |
| 6 | 1–4 | `+5V` | J1.3 |
| 6 | 6–11 | *(unused)* | U1.5 |
| 6 | 13–40 | `+3V3` | U1.36 |
| 7 | 1–11 | `/SDA` | U1.6, J1.4 |
| 7 | 13–40 | *(unused)* | U1.35 |
| 8 | 1–11 | `/SCL` | U1.7, J1.5 |
| 8 | 13–40 | *(unused)* | U1.34 |
| 9 | 1–4 | `/IRQ` | J1.6 |
| 9 | 6–11 | `GND` | U1.8 |
| 9 | 13–40 | *(no-connect)* | **U1.33 AGND — must stay isolated** |
| 10 | 1–11 | `/IRQ` | U1.9 |
| 10 | 13–40 | *(unused)* | U1.32 |
| 11–13, 15–18 | 1–11 / 13–40 | *(unused Pico pins)* | one per side, bare |
| **14** | **all (uncut)** | `GND` | U1.13, U1.28 |
| **19** | **all (uncut)** | `GND` | U1.18, U1.23 |
| 20 | 1–11 | *(unused)* | U1.19 |
| 20 | 13–40 | `/ENC_B` | U1.22, R5.1 |
| 21 | 1–11 | *(unused)* | U1.20 |
| 21 | 13–25 | `/ENC_A` | U1.21, R4.1 |
| 21 | 27–40 | `GND` | J2.5 |
| 22 | all | `/ENC_B_RAW` | R5.2, R2.2, J2.4 |
| 23 | all | `/ENC_A_RAW` | R4.2, R1.2, J2.3 |
| 24 | 1–26 | `+3V3` | R7.1, R2.1, R1.1, C2.1 |
| 24 | 28–40 | `GND` | J2.2 |
| 25 | 1–11 | `Net-(D1-A)` | R7.2, D1.2 |
| 25 | 13–40 | `+5V` | J2.1 |
| 26 | all | `GND` | D1.1, D2.1, C2.2 |
| 27 | all | `Net-(D2-A)` | D2.2, R8.2 |
| 28 | all | `/LNK` | R8.1 |
| 29–40 | all | *(spare board)* | — |

63 strip segments in total, across 1331 holes.

## Placement

Pad 1 sits at the stated hole for every part. **All six resistors stand on end**
— this is the Veroboard idiom and it is what stops them shorting along a strip.

| Ref | Value | Footprint | Pad 1 | Occupies |
|---|---|---|---|---|
| U1 | Pico | `RaspberryPi_Pico_Common_THT` | (9,2) | cols 9 & 16, rows 2–21 |
| J1 | XH2.54 6-pin | `JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical` | (2,4) | col 2, rows 4–9 |
| J2 | 5-pin header | `PinHeader_1x05_P2.54mm_Vertical` | (28,25) | col 28, rows 21–25, **pin 1 at the bottom** |
| R1 | 4.7k | `R_Axial_..._P2.54mm_Vertical` | (24,24) | col 24, rows 23–24 |
| R2 | 4.7k | `R_Axial_..._P5.08mm_Vertical` | (22,24) | col 22, rows 22–24 |
| R4 | 330R | `R_Axial_..._P5.08mm_Vertical` | (20,21) | col 20, rows 21–23 |
| R5 | 330R | `R_Axial_..._P5.08mm_Vertical` | (18,20) | col 18, rows 20–22 |
| R7 | 1k | `R_Axial_..._P2.54mm_Vertical` | (2,24) | col 2, rows 24–25 |
| R8 | 1k | `R_Axial_..._P2.54mm_Vertical` | (2,28) | col 2, rows 27–28 |
| C1 | 10uF 25V | `wheel-module:CP_Radial_D4.0mm_P2.50mm` | (18,3) | col 18, rows 3–4, **pad 1 = + = row 3** |
| C2 | 100nF | `C_Disc_D5.0mm_W2.5mm_P5.00mm` | (26,24) | col 26, rows 24–26 |
| D1 | power LED | `LED_D3.0mm` | (4,26) | col 4, rows 25–26, pad 1 = cathode = GND |
| D2 | link LED | `LED_D3.0mm` | (6,26) | col 6, rows 26–27, pad 1 = cathode = GND |

**C1 is polarised.** It is a D4x7 aluminium electrolytic, not the ceramic disc the
first revision carried. Pad 1 is the **+** lead and belongs on row 3 (the `+5V` strip);
the lead beside the printed stripe is **−** and goes to row 4 (`GND`). Fitted the wrong
way round it can vent. Its footprint is drawn project-local, in
`libraries/wheel-module.pretty`: no stock `CP_Radial` pairs a 4 mm can with the
2.50 mm pitch the 2.54 mm grid needs, and the stock 5 mm can is 1 mm too wide —
wide enough that its courtyard overlapped the Pico here and pushed C1 three holes
right for no physical reason.

Two parts are very slightly off-grid and this is fine — the leads bend:

- `J1` is a 2.50 mm connector on a 2.54 mm grid: pin 6 lands 0.2 mm above row 9,
  cumulative over six pins. XH pins are 0.6 mm in 1.0 mm holes.
- `C1` (2.50 mm) and `C2` (5.00 mm) are 0.04 mm and 0.08 mm out respectively.

`R4` and `R5` are the nicest part of this layout: they reach straight from the
Pico's `/ENC_A`/`/ENC_B` pins down to the `_RAW` rows with **no link wire at
all**, so the two noise-sensitive nets are pure copper.

## Link wires — 8 of them

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
| 1 | `+5V` | red | (2,6) `J1.3` | (19,3) | console 5V over the module to the `+5V` rail |
| 2 | `/IRQ` | yellow | (2,9) `J1.6` | (4,10) | J1's IRQ pin down to the Pico's |
| 3 | `+5V` | red | (27,3) | (28,25) `J2.1` | rail down to the encoder connector |
| 4 | `+3V3` | red | (18,6) | (18,24) | Pico 3V3 out to the pull-up rail |
| 5 | `/LNK` | green | (6,5) | (6,28) | Pico GP2 down to the LED resistor |
| 6 | `GND` | blue | (7,4) | (7,26) | GND spine — **solder it also at rows 9, 14 and 19 on the way past** |
| 7 | `GND` | blue | (27,21) | (27,26) | `J2.5` cable shield to GND |
| 8 | `GND` | blue | (28,24) | (28,26) | `J2.2` encoder GND to GND |

Wire 6 is one length soldered at five holes — rows 4, 9, 14, 19 and 26. Those
three intermediate joints are what tie the Pico's GND rows into one bus; skipping
any of them leaves that row floating. (The board file models them as three extra
zero-length links, which is why the netlist counts eleven and this table eight.)

Wire 1 is the long one. It runs from `J1.3` up the outside of column 2, across
above the module in the gutter between rows 1 and 2, and down to (19,3). Its
copper track passes 1.27 mm from the row-2 Pico pins — 0.32 mm of clearance — so
keep the physical wire pulled up against the module's top edge rather than
letting it wander down over the pins. It crosses wires 5 and 6 on the way; all
three are insulated, so let 1 lie over them.

Wire 8 passes directly over `J2` pin 1, where wire 3 lands. Both are insulated —
let 8 lie over 3 rather than trying to dodge it.

## Optical Encoder (J2) & Console (J1) External Wiring

### Optical Encoder Wiring (`J2` — 5-Pin Header)

Target Encoder: **E38S6G5-600B-G24N** (NPN open-collector, 600 P/R).

| `J2` Pin | Stripboard Position (Col, Row) | Board Net | Encoder Wire Color | Function / Signal Path |
|---|---|---|---|---|
| **Pin 1** | **(28, 25)** *(Bottom)* | `+5V` | **Red** | Encoder DC Power Supply (+5V) |
| **Pin 2** | **(28, 24)** | `GND` | **Black** | Encoder Power Ground (0V) |
| **Pin 3** | **(28, 23)** | `/ENC_A_RAW` | **White** | Phase A &rarr; pull-up `R1` (4.7k) &rarr; `R4` (330R) &rarr; Pico `GP16` |
| **Pin 4** | **(28, 22)** | `/ENC_B_RAW` | **Green** | Phase B &rarr; pull-up `R2` (4.7k) &rarr; `R5` (330R) &rarr; Pico `GP17` |
| **Pin 5** | **(28, 21)** *(Top)* | `GND` (Shield) | **Bare / Braid** | Cable shield drain (single-point to board GND) |

#### Physical Header Orientation (Component Side, Pico USB UP):
```text
               [ Pico USB Top ]
  
  (Col 28, Row 21)  [ Pin 5 ]  <--- BARE BRAID (Cable Shield)
  (Col 28, Row 22)  [ Pin 4 ]  <--- GREEN      (Phase B)
  (Col 28, Row 23)  [ Pin 3 ]  <--- WHITE      (Phase A)
  (Col 28, Row 24)  [ Pin 2 ]  <--- BLACK      (Ground 0V)
  (Col 28, Row 25)  [ Pin 1 ]  <--- RED        (+5V Power)
  
              [ Bottom Edge ]
```

- **Shield Ground:** Terminate shield braid to Pin 5 *at this board end only* to prevent ground loops along the 2 m cable.
- **Open-Collector Logic:** Encoder outputs pull to GND; board pull-ups (`R1`, `R2`) pull up to +3.3V, ensuring Pico GPIO safety.
- **Pre-Flight DMM Checks:** Power board, measure Pin 1 &rarr; Pin 2 (+5.0V) and Pins 3/4 &rarr; GND (+3.3V) before plugging encoder in.

### Console Harness Wiring (`J1` — XH2.54 6-Pin Connector)

| `J1` Pin | Position (Col, Row) | Net | Function |
|---|---|---|---|
| **Pin 1** | **(2, 4)** *(Top)* | `GND` | Common system ground (Row 4 GND bus) |
| **Pin 2** | **(2, 5)** | `NC (Isolated)` | Console 3.3V &mdash; **must stay isolated** |
| **Pin 3** | **(2, 6)** | `+5V` | Console 5V DC power in &rarr; Pico VSYS |
| **Pin 4** | **(2, 7)** | `/SDA` | I²C Data &rarr; Pico `GP4` |
| **Pin 5** | **(2, 8)** | `/SCL` | I²C Clock &rarr; Pico `GP5` |
| **Pin 6** | **(2, 9)** *(Bottom)* | `/IRQ` | Interrupt line &rarr; Pico `GP6` |

## Build order

1. **Make all 23 cuts first**, before any part goes in. Check each one for
   continuity across the gap — a partial cut is the hardest fault to find later.
2. **Fit the Pico on female headers**, not soldered down. Two GND strips and the
   whole cut column run underneath it.
3. **Resistors, LEDs, caps.** All resistors vertical. Watch LED polarity: pad 1
   is the cathode and goes to the GND row (26) for both.
4. **`J1` and `J2`.**
5. **Link wires last.** They go on the *solder* side, so they follow the parts
   rather than preceding them: each end lands in the named hole and is soldered
   to that strip alongside the component lead already there. Strip and tin both
   ends first — a wire soldered onto an already-crowded joint is the easiest one
   to lift by accident.
6. Before power-up, check with a meter: `+5V` to `GND` open, `+3V3` to `GND`
   open, and **`U1.33` (AGND) isolated from GND** — that last one is the specific
   thing this layout's row-9 cut exists to guarantee.

## Verification state

- `kicad-cli pcb drc`: **0 errors, 0 unconnected pads, 0 footprint errors.**
- Strip audit (`every segment carries exactly one net`): **clean**, including the
  two isolation invariants above.
- 240 DRC *warnings* remain, all `via_dangling`/`track_dangling` plus three
  pre-existing `lib_footprint_mismatch`. These are expected — see `CLAUDE.md`.
