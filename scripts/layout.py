"""Stripboard layout for the Wheel Module (M3) encoder sensor board.

Pure data.  The engine that turns it into copper lives in
``~/KiCad/kicad-stripboard`` and is shared with the other board projects:

    ~/KiCad/kicad-stripboard/build.py \
        scripts/layout.py \
        project/haptic-console-wheel-module-stripboard.kicad_pcb \
        --from project/haptic-console-wheel-module-perfboard.kicad_pcb

Grid: col c -> x = c * 2.54 mm, row r -> y = r * 2.54 mm; cols 1..28, rows 1..30,
board 73.66 x 78.74 mm with a one-hole margin.  Strips run horizontally on B.Cu,
link wires on F.Cu.  Human-readable build guide: ``docs/stripboard-wiring.md``.
"""
from stripboard import BoardSpec, Grid, Link, Placement

GRID = Grid(cols=28, rows=30)

# --- U1, the Pico ------------------------------------------------------------
# Pin 1 at (col 9, row 3), unrotated.  Left pins 1..20 run down col 9 on rows
# 3..22; right pins 21..40 run back up col 16.
PICO_COL_L, PICO_COL_R, PICO_ROW0 = 9, 16, 3


def pico_row(pin):
    return PICO_ROW0 + (pin - 1 if pin <= 20 else 40 - pin)


# --- What each row carries ---------------------------------------------------
# Documentation, not an input: the engine derives every strip's net from the
# pads that actually land on it.  Kept because it is how the layout was reasoned
# about, and because a mismatch between this and the audit output is a signal.
#
# Rows 5/15/20 are GND on BOTH sides of the Pico (pins 3/38, 13/28, 18/23), so
# leaving them uncut buys six GND connections and the GND bus for free.  Row 10
# is GND (pin 8) on the left and AGND (pin 33) on the right and MUST be cut --
# AGND is a design-invariant no-connect, and tying it to GND re-creates the
# power_out/power_out ERC violation recorded in CLAUDE.md.
ROW_NET = {
    2:  "+5V",          # rail above the Pico, reached only by link wires
    4:  "+5V",          # U1.39 (right segment)
    5:  "GND",          # U1.3 / U1.38          -- uncut
    6:  "/LNK",         # U1.4 (middle segment); left-of-cut = J1.2, no-connect
    7:  "+3V3",         # U1.36 (right);         left-of-cut = J1.3 +5V stub
    8:  "/SDA",         # U1.6  + J1.4
    9:  "/SCL",         # U1.7  + J1.5
    10: "GND",          # U1.8 middle; AGND right (isolated); J1.6 stub left
    11: "/IRQ",         # U1.9  + link from J1.6
    15: "GND",          # U1.13 / U1.28         -- uncut
    20: "GND",          # U1.18 / U1.23         -- uncut
    21: "/ENC_B",       # U1.22 (right segment)
    22: "/ENC_A",       # U1.21 (right);         J2.5 stub right of the col-26 cut
    23: "/ENC_B_RAW",
    24: "/ENC_A_RAW",
    25: "+3V3",         # R1.1 R2.1 C2.1;        J2.2 stub right of the col-27 cut
    26: "+5V",          # right of the col-12 cut (J2.1); left = Net-(D1-A)
    27: "GND",
    28: "Net-(D2-A)",
    29: "/LNK",
}

# --- Cuts --------------------------------------------------------------------
MAIN_CUT_COL = 12       # between the Pico's two pin columns
LEFT_CUT_COL = 5        # between J1 and the Pico

CUTS = (
    # main cut: every Pico row except the three GND rows, plus row 26
    [(MAIN_CUT_COL, r) for r in range(3, 23) if r not in (5, 15, 20)]
    + [(MAIN_CUT_COL, 26)]
    # left cut: the rows where J1's pin order disagrees with the Pico's
    + [(LEFT_CUT_COL, r) for r in (6, 7, 10)]
    # right cuts: isolate J2's two GND pins from /ENC_A and +3V3
    + [(26, 22), (27, 25)]
)

# --- Footprints --------------------------------------------------------------
# Every two-pad part stands on end so its pads land on two different rows.  Lying
# flat -- which is what the point-to-point perfboard layout does -- would put both
# pads on the same strip and short the part out.
RV254 = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical"
RV508 = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P5.08mm_Vertical"
CD250 = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm"
CD500 = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"

PLACE = {
    # pad 1 goes exactly on (col, row); footprint=None keeps the existing one
    "U1": Placement(9, 3, 0),
    "J1": Placement(2, 5, 270),        # pins 1..6 -> rows 5..10 (2.50 mm pitch)
    "J2": Placement(28, 26, 180),      # pins 1..5 -> rows 26, 25, 24, 23, 22
    # encoder cluster, right region, >= 2 columns apart (courtyards, not holes,
    # decide spacing)
    "R5": Placement(18, 21, 270, RV508),   # /ENC_B r21 -> /ENC_B_RAW r23
    "R4": Placement(20, 22, 270, RV508),   # /ENC_A r22 -> /ENC_A_RAW r24
    "R2": Placement(22, 25, 90, RV508),    # +3V3   r25 -> /ENC_B_RAW r23
    "R1": Placement(24, 25, 90, RV254),    # +3V3   r25 -> /ENC_A_RAW r24
    "C2": Placement(26, 25, 270, CD500),   # +3V3   r25 -> GND         r27
    "C1": Placement(18, 4, 270, CD250),    # +5V    r4  -> GND         r5
    # LED chain, left region
    "R7": Placement(2, 25, 270, RV254),    # +3V3   r25 -> Net-(D1-A)  r26
    "D1": Placement(4, 27, 90),            # GND    r27 -> Net-(D1-A)  r26
    "D2": Placement(6, 27, 270),           # GND    r27 -> Net-(D2-A)  r28
    "R8": Placement(2, 29, 90, RV254),     # /LNK   r29 -> Net-(D2-A)  r28
}

# R4 and R5 are the nicest part of this layout: they reach from the Pico's
# /ENC_A and /ENC_B pins straight down to the _RAW rows with no link wire at
# all, so the two noise-sensitive nets are pure copper.

# --- Link wires --------------------------------------------------------------
# Fractional coordinates are gutter lines (half-pitch, between hole lines).
# Links travel only along those, with 1.27 mm step-in segments, so they never
# run down a hole column and touch a foreign net.
LINKS = [
    Link("+5V",  [(2, 6.97), (1.5, 6.97), (1.5, 2), (2, 2)]),     # J1.3 -> +5V rail
    Link("/IRQ", [(2, 9.92), (2.5, 9.92), (2.5, 11), (4, 11)]),   # J1.6 -> /IRQ
    Link("+5V",  [(19, 4), (19.5, 4), (19.5, 2), (19, 2)]),       # U1.39 VSYS -> rail
    Link("+5V",  [(27, 2), (27.5, 2), (27.5, 26), (28, 26)]),     # rail -> J2.1
    Link("+3V3", [(18, 7), (17.5, 7), (17.5, 25), (18, 25)]),     # U1.36 -> pull-up rail
    Link("/LNK", [(6, 6), (6.5, 6), (6.5, 29), (6, 29)]),         # U1.4 -> LED resistor
    Link("GND",  [(7, 5), (7.5, 5), (7.5, 27), (7, 27)]),         # GND spine, rows 5..27
    Link("GND",  [(7, 10), (7.5, 10)]),                           #   tap row 10
    Link("GND",  [(7, 15), (7.5, 15)]),                           #   tap row 15
    Link("GND",  [(7, 20), (7.5, 20)]),                           #   tap row 20
    Link("GND",  [(27, 22), (26.5, 22), (26.5, 27), (27, 27)]),   # J2.5 shield -> GND
    Link("GND",  [(28, 25), (28.5, 25), (28.5, 27), (28, 27)]),   # J2.2 -> GND
]

SPEC = BoardSpec(
    grid=GRID,
    place=PLACE,
    cuts=CUTS,
    links=LINKS,
    # Row 2 is the +5V rail, reached only over link wires.  No pad sits on it,
    # so its net cannot be inferred and it would land on net 0 -- making every
    # link that touches it read as a short.
    row_force_net={2: "+5V"},
    # The Pico's antenna keep-out forbids tracks between its pin rows.  On
    # Veroboard the strips run under the module by construction, so it cannot be
    # honoured; and this is a non-W Pico with no radio, so it protects nothing.
    disable_rule_areas=[("U1", "Antenna")],
    isolated=[
        ("U1.33", "AGND is a no-connect; tying it to GND is the power_out/power_out ERC"),
        ("J1.2",  "hub 3.3V stays unconnected; the Pico makes its own 3.3V"),
    ],
)
