"""Stripboard layout for the Wheel Module (M3) encoder sensor board.

Pure data.  The engine that turns it into copper lives in
``~/KiCad/kicad-stripboard`` and is shared with the other board projects:

    ~/KiCad/kicad-stripboard/build.py \
        scripts/layout.py \
        project/haptic-console-wheel-module-stripboard.kicad_pcb \
        --from project/haptic-console-wheel-module-perfboard.kicad_pcb

Grid: col c -> x = c * 2.54 mm, row r -> y = r * 2.54 mm; cols 1..40, rows 1..40,
board 104.14 mm square with a one-hole margin.  Strips run horizontally on B.Cu,
link wires on F.Cu.  Human-readable build guide: ``docs/stripboard-wiring.md``
(and ``docs/stripboard-wiring.html``).

The grid is the size of the stock the board is actually built on -- a 40 x 40
hole Veroboard.  The circuit occupies cols 1..28 / rows 1..28 in the top-left;
everything beyond that is spare board.  Strips still run the *full* width, so the
right-hand end of every row is live copper continuous with the part of the row
the circuit uses.
"""

import os
from stripboard import BoardSpec, Grid, Link, Placement

GRID = Grid(cols=40, rows=40)

# --- U1, the Pico ------------------------------------------------------------
# Pin 1 at (col 9, row 2), unrotated.  Left pins 1..20 run down col 9 on rows
# 2..21; right pins 21..40 run back up col 16.
#
# Row 1 is left empty on purpose.  The module body is 51 mm for 19 pin pitches
# (48.26 mm), so it overhangs its end rows by 1.37 mm: the body edge sits at
# y = 3.71 mm and a row-1 hole's copper ends at 3.29 mm.  0.42 mm of daylight,
# and only usable at all because the Pico is socketed on 8.5 mm headers and
# overhangs in mid-air.  Nothing is soldered there.
PICO_COL_L, PICO_COL_R, PICO_ROW0 = 9, 16, 2


def pico_row(pin):
    return PICO_ROW0 + (pin - 1 if pin <= 20 else 40 - pin)


# --- What each row carries ---------------------------------------------------
# Documentation, not an input: the engine derives every strip's net from the
# pads that actually land on it.  Kept because it is how the layout was reasoned
# about, and because a mismatch between this and the audit output is a signal.
#
# Rows 4/14/19 are GND on BOTH sides of the Pico (pins 3/38, 13/28, 18/23), so
# leaving them uncut buys six GND connections and the GND bus for free.  Row 9
# is GND (pin 8) on the left and AGND (pin 33) on the right and MUST be cut --
# AGND is a design-invariant no-connect, and tying it to GND re-creates the
# power_out/power_out ERC violation recorded in CLAUDE.md.
ROW_NET = {
    3:  "+5V",          # U1.39 VSYS + C1.1 (right segment) -- the +5V rail
    4:  "GND",          # U1.3 / U1.38 + J1.1    -- uncut
    5:  "/LNK",         # U1.4 (middle segment); left-of-cut = J1.2, no-connect
    6:  "+3V3",         # U1.36 (right);         left-of-cut = J1.3 +5V stub
    7:  "/SDA",         # U1.6  + J1.4
    8:  "/SCL",         # U1.7  + J1.5
    9:  "GND",          # U1.8 middle; AGND right (isolated); J1.6 stub left
    10: "/IRQ",         # U1.9  + link from J1.6
    14: "GND",          # U1.13 / U1.28          -- uncut
    19: "GND",          # U1.18 / U1.23          -- uncut
    20: "/ENC_B",       # U1.22 (right segment)
    21: "/ENC_A",       # U1.21 (right);         J2.5 stub right of the col-26 cut
    22: "/ENC_B_RAW",
    23: "/ENC_A_RAW",
    24: "+3V3",         # R1.1 R2.1 C2.1;        J2.2 stub right of the col-27 cut
    25: "+5V",          # right of the col-12 cut (J2.1); left = Net-(D1-A)
    26: "GND",
    27: "Net-(D2-A)",
    28: "/LNK",
}

# --- Cuts --------------------------------------------------------------------
MAIN_CUT_COL = 12       # between the Pico's two pin columns
LEFT_CUT_COL = 5        # between J1 and the Pico

CUTS = (
    # main cut: every Pico row except the three GND rows, plus row 25
    [(MAIN_CUT_COL, r) for r in range(2, 22) if r not in (4, 14, 19)]
    + [(MAIN_CUT_COL, 25)]
    # left cut: the rows where J1's pin order disagrees with the Pico's
    + [(LEFT_CUT_COL, r) for r in (5, 6, 9)]
    # right cuts: isolate J2's two GND pins from /ENC_A and +3V3
    + [(26, 21), (27, 24)]
)

# --- Footprints --------------------------------------------------------------
# Every two-pad part stands on end so its pads land on two different rows.  Lying
# flat -- which is what the point-to-point perfboard layout does -- would put both
# pads on the same strip and short the part out.
RV254 = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical"
RV508 = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P5.08mm_Vertical"
CP250 = "wheel-module:CP_Radial_D4.0mm_P2.50mm"    # polarised: pad 1 = +, pad 2 = -
CD500 = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"

PLACE = {
    # pad 1 goes exactly on (col, row); footprint=None keeps the existing one
    "U1": Placement(9, 2, 0),
    "J1": Placement(2, 4, 270),        # pins 1..6 -> rows 4..8.92 (2.50 mm pitch)
    "J2": Placement(28, 25, 180),      # pins 1..5 -> rows 25, 24, 23, 22, 21
    # encoder cluster, right region, >= 2 columns apart (courtyards, not holes,
    # decide spacing)
    "R5": Placement(18, 20, 270, RV508),   # /ENC_B r20 -> /ENC_B_RAW r22
    "R4": Placement(20, 21, 270, RV508),   # /ENC_A r21 -> /ENC_A_RAW r23
    "R2": Placement(22, 24, 90, RV508),    # +3V3   r24 -> /ENC_B_RAW r22
    "R1": Placement(24, 24, 90, RV254),    # +3V3   r24 -> /ENC_A_RAW r23
    "C2": Placement(26, 24, 270, CD500),   # +3V3   r24 -> GND         r26
    # C1 is the D4x7 electrolytic, drawn project-local because no stock CP_Radial
    # pairs a 4 mm can with a 2.50 mm pitch, and only 2.50 keeps the pads on the
    # 2.54 grid.  Its 4.59 mm courtyard clears U1 by 0.18 mm here; the 5 mm can
    # did not, which is the whole reason the accurate body is worth drawing.
"C1": Placement(18, 3, 270, CP250),    # +5V    r3  -> GND         r4  (+ on r3)
    # LED chain, left region
    "R7": Placement(2, 24, 270, RV254),    # +3V3   r24 -> Net-(D1-A)  r25
    "D1": Placement(4, 26, 90),            # GND    r26 -> Net-(D1-A)  r25
    "D2": Placement(6, 26, 270),           # GND    r26 -> Net-(D2-A)  r27
    "R8": Placement(2, 28, 90, RV254),     # /LNK   r28 -> Net-(D2-A)  r27
}

# R4 and R5 are the nicest part of this layout: they reach from the Pico's
# /ENC_A and /ENC_B pins straight down to the _RAW rows with no link wire at
# all, so the two noise-sensitive nets are pure copper.

# --- Link wires --------------------------------------------------------------
# Fractional coordinates are gutter lines (half-pitch, between hole lines).
# Links travel only along those, with 1.27 mm step-in segments, so they never
# run down a hole column and touch a foreign net.
LINKS = [
    # +5V has no full-width strip.  It cannot have one: a strip that spans the
    # Pico is only safe on a row whose two pins are the same net, and the only
    # such rows are the three GND ones.  So the rail is row 3's right-hand
    # segment -- U1.39 VSYS and C1.1 sit on it directly -- and the hub's 5 V,
    # which arrives on the far left at J1.3, is carried over the top of the
    # module to reach it.  The gutter run at row 1.5 passes 1.27 mm from the
    # row-2 pins (0.32 mm of copper clearance) and touches no hole.
    Link("+5V",  [(2, 5.97), (1.5, 5.97), (1.5, 1.5), (18.5, 1.5),
                  (18.5, 3), (19, 3)], z_tier=1.0),                # J1.3 -> +5V rail
    Link("/IRQ", [(2, 8.92), (2.5, 8.92), (2.5, 10), (4, 10)]),   # J1.6 -> /IRQ
    Link("+5V",  [(27, 3), (27.5, 3), (27.5, 25), (28, 25)]),     # rail -> J2.1
    Link("+3V3", [(18, 6), (17.5, 6), (17.5, 24), (18, 24)]),     # U1.36 -> pull-up rail
    Link("/LNK", [(6, 5), (6.5, 5), (6.5, 28), (6, 28)]),         # U1.4 -> LED resistor
    Link("GND",  [(7, 4), (7.5, 4), (7.5, 26), (7, 26)]),         # GND spine, rows 4..26
    # One physical wire runs the length of the spine and is soldered at each of
    # rows 9, 14 and 19 on the way past.  These three links are those solder
    # joints, not wires of their own, so they draw no jumper.
    Link("GND",  [(7, 9), (7.5, 9)], wire=False),                 #   tap row 9
    Link("GND",  [(7, 14), (7.5, 14)], wire=False),               #   tap row 14
    Link("GND",  [(7, 19), (7.5, 19)], wire=False),               #   tap row 19
    Link("GND",  [(27, 21), (26.5, 21), (26.5, 26), (27, 26)]),   # J2.5 shield -> GND
    # Passes directly over J2 pin 1, where the +5V wire lands.  The copper track
    # dodges into the col-28.5 gutter; the insulated wire simply lies over it,
    # so lift the model a tier to render the over/under cleanly.
    Link("GND",  [(28, 24), (28.5, 24), (28.5, 26), (28, 26)], z_tier=1.0),
]

SPEC = BoardSpec(
    grid=GRID,
    # C1's can is drawn in a project-local library: no stock CP_Radial pairs a
    # 4 mm body with the 2.50 mm pitch the 2.54 grid needs.  Stock libraries all
    # live under one root, so this one has to be named explicitly.
    footprint_libs={
        "wheel-module": os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "libraries", "wheel-module.pretty"),
    },
    place=PLACE,
    cuts=CUTS,
    links=LINKS,
    # The Pico's antenna keep-out forbids tracks between its pin rows.  On
    # Veroboard the strips run under the module by construction, so it cannot be
    # honoured; and this is a non-W Pico with no radio, so it protects nothing.
    disable_rule_areas=[("U1", "Antenna")],
    isolated=[
        ("U1.33", "AGND is a no-connect; tying it to GND is the power_out/power_out ERC"),
        ("J1.2",  "hub 3.3V stays unconnected; the Pico makes its own 3.3V"),
    ],
    # The link wires are also drawn as physical jumper wires, in the colours of
    # the boxed kit.  Console convention, shared with the control unit so the
    # same net is the same colour on every board: red for power, blue for GND
    # (the kit has no black), yellow for the I2C/IRQ bus, and one of
    # white/orange/green for each remaining signal.
    #
    # They run on the SOLDER side.  The component side is crowded -- the Pico
    # spans twenty rows, and J1, J2 and the LEDs sit on the edges the long links
    # follow -- so front-side wires would lie across component bodies.  The back
    # is flat: insulated wire over a copper strip touches nothing.
    wire_side="back",
    wire_colors={
        "+5V":  "red",
        "+3V3": "red",
        "GND":  "blue",
        "/IRQ": "yellow",
        "/LNK": "green",
    },
)
