# CLAUDE.md - Haptic Console Wheel Module (M3)

Guidance for working on this KiCad project. See `README.md` for the circuit itself.
Conventions inherited from `../control-unit-kicad/CLAUDE.md`.

## Rule #1: don't hand-edit .kicad_sch / .kicad_pcb

The project owner has said this emphatically. **Never modify the schematic or PCB
S-expression files with Python scripts or manual text edits.** Use the KiCad MCP tools,
`kicad-cli`, or the GUI.

Why: KiCad 9/10 symbol instances need exact per-pin entries and full property sets.
Edits that look structurally valid can still desync from what KiCad's own writer
produces. Pins silently drop out of the netlist, or the file fails to load.

**Exception taken on 2026-08-27:** a `(title_block ...)` node was inserted by hand
directly after `(paper "A4")`, because no MCP tool exposes the title block. It is pure
sheet metadata and touches no symbol, pin, or net. It was verified afterwards with
`kicad-cli sch erc` (0 violations) and by diffing the exported netlist against the
pre-edit export (identical, 245 net names). Do not treat this as licence to hand-edit
anything that carries connectivity.

## Project creation gotchas (2026-08-27, first session)

Three traps hit while creating this project. All cost real debugging time.

### 1. `create_kicad_project` clones a template with content in it

The `kicad-mcp-server` `create_kicad_project` tool works by copying a KiCad template
project. Here it copied **Arduino_Mega**, producing an 82 KB schematic and a 101 KB PCB
full of Arduino shield geometry. Delete `.kicad_sch` and `.kicad_pcb` afterwards and let
`schematic_place_symbol` create a fresh schematic on first call. Keep the `.kicad_pro`
(it is only settings) but see trap 2.

### 2. `.kicad_pro` root-sheet UUID must match the schematic root UUID

This is the one that wasted the most time. After deleting the template schematic, the
`.kicad_pro` still carried the **template's** root sheet UUID in its `sheets` key, while
the newly created `.kicad_sch` had a different root UUID. KiCad could then not resolve
any symbol instance path.

Symptom: `kicad-cli sch export netlist` prints
`Warning: schematic has annotation errors` and exports **zero components**, while
`kicad-cli sch erc` cheerfully reports 0 violations. A clean ERC does not prove the
schematic is sound. Always export the netlist and read it.

Fix (`.kicad_pro` is JSON project metadata, not an S-expression, so editing it is fine):

```python
root = re.search(r'\(uuid "([0-9a-f-]+)"\)', open(sch).read()).group(1)
pro['sheets'] = [[root, 'Root']]
```

### 3. `Device:CP` caches as an empty stub with zero pins

`schematic_place_symbol` cached `Device:CP` (polarised capacitor) into `lib_symbols` as
`(symbol "Device:CP" (in_bom yes) (on_board yes) (symbol "CP_0_1"))` - **no pins at
all**. `schematic_get_pin_positions` returned an empty list, and the part would have
vanished from the netlist. `Device:C` caches correctly.

The cause is that `CP` is an `extends` symbol; the tool does not resolve inherited pins.
**After placing any symbol, audit the cached pin count**, especially for `extends`
symbols:

```python
starts=[(m.start(),m.group(1)) for m in re.finditer(r'\(symbol "([A-Za-z_0-9]+:[^"]+)"',src)]
for i,(pos,name) in enumerate(starts):
    end = starts[i+1][0] if i+1<len(starts) else len(src)
    print(name, src[pos:end].count('(pin '))
```

Here C1 was re-placed as `Device:C` (10uF ceramic is fine for bulk decoupling and avoids
the polarity question entirely).

## ERC gotchas specific to the Pico symbol

`MCU_Module:RaspberryPi_Pico` declares **pin 3 (GND) and pin 33 (AGND) as
`power_out`**, not `power_in`. Tying both to the GND net therefore triggers
`Pins of type Power output and Power output are connected`.

Since this board uses no ADC at all, AGND is a **no-connect**. If a future revision uses
the ADC, tie AGND to GND and expect to suppress that specific ERC rule.

The `+5V` net also needs a `power:PWR_FLAG`. Everything on it is either passive
(`J1`, `J2`, `C1`) or `power_in` (Pico VSYS), so without a flag ERC reports
`Input Power pin not driven by any Output Power pins`. `+3V3` needs no flag because
Pico pin 36 is a genuine `power_out`.

## Library setup

All symbols and footprints are **stock KiCad 10**. Nothing custom is vendored, so
`libraries/` is currently empty.

Note that `Connector_JST.kicad_sym` does **not** exist in this KiCad 10 install; only
the footprint library `Connector_JST.pretty` does. The XH connector therefore uses the
`Connector_Generic:Conn_01x06` symbol with a `Connector_JST:` footprint. This matches
what the control unit project does.

## Verification workflow

`kicad-cli` is at `/opt/homebrew/bin/kicad-cli` (KiCad 10.0.5). **Both** env vars must
be set or you get spurious library-resolution violations:

```bash
export KICAD_SYMBOL_DIR=/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols
export KICAD_FOOTPRINT_DIR=/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints
kicad-cli sch erc --format report project/haptic-console-wheel-module.kicad_sch -o docs/erc-report.txt
kicad-cli sch export netlist --format kicadsexpr project/haptic-console-wheel-module.kicad_sch -o docs/netlist.net
kicad-cli sch export pdf project/haptic-console-wheel-module.kicad_sch -o renders/schematic-v1.pdf
pdftoppm -png -r 150 renders/schematic-v1.pdf renders/schematic-v1
```

Treat a change as verified only when ERC is clean **and** the netlist still lists every
component with the expected nodes. No SVG to PNG converter is installed on this machine;
go through PDF plus `pdftoppm`.

## Design invariants (do not break these)

- Encoder A/B/Z pull-ups go to **3.3V only**, never to the encoder supply rail. This is
  what makes a 5-24V open-collector encoder safe on 3.3V GPIO.
- `J1` pin 2 (3.3V from the hub) stays **unconnected**. The Pico is powered from 5V into
  VSYS and generates its own 3.3V. Do not create a second competing power path.
- I2C bus pull-ups belong on the master/hub board, not on this module.
- Any future module signal must keep the XH2.54 6-pin standard v1.1 pinout.

## Perfboard layout (2026-08-28 session)

Placed with the `kicad-mcp` tools into
`project/haptic-console-wheel-module-perfboard.kicad_pcb`. 28x28 holes at 2.54mm
(71.12 x 71.12 mm cut). Build guide: `docs/perfboard-wiring.md`.

**Every footprint in this project has pad 1 at local (0,0)** - Pico, JST XH, pin
header, axial resistors, disc caps, LEDs, all of them. That makes grid placement
trivial: put the footprint origin exactly on the target hole and pad 1 lands there.
Rotation then follows the control-unit mapping (rot90: `world = (ox + ly, oy - lx)`),
and rot180/rot270 behave as the plain rotation matrix predicts. Verified by
recomputing every pad's world position from the saved file rather than trusting it.

**`pcb_set_board_outline` must not be given a repeated closing point.** Passing
`[[0,0],[w,0],[w,h],[0,h],[0,0]]` produces a zero-length segment and DRC reports
both `invalid_outline: null or very small length` and `self-intersecting`. Pass the
four corners only; the tool closes the polygon itself.

**Courtyards, not just holes, decide spacing.** Two `R_Axial_DIN0207_..._P10.16mm`
resistors on adjacent 2.54mm rows pass a hole-collision check but fail
`courtyards_overlap` - and physically the bodies touch. Keep axial parts **two rows
apart**. Likewise the Pico footprint's courtyard extends about 2mm past its pad
columns, so a resistor pad one column outside the Pico's pin column still trips
`pth_inside_courtyard`. Leave two columns.

**Verify placement by reading pads back, not by trusting the move calls.** Same
lesson as the schematic netlist: recompute world positions, check for shared holes,
off-grid pads, and out-of-bounds, then run DRC. A move that "succeeded" can still
land somewhere useless.

**32 unconnected pads in the perfboard DRC report is the correct result.** The board
is hand-wired and has no copper traces. Do not try to "fix" it.

## TODO

- [ ] Cosmetic pass in the GUI: auto-placed reference/value text overlaps net labels
      around J1, J2, R1-R3 and the LEDs. Same issue on the perfboard silkscreen
      (D2's reference sits under J1's outline) - three `silk_overlap` warnings.
- [ ] Perfboard hole grid: the background via grid the control unit uses for its
      render trick is **not** added here. Worth doing if the render is going into the
      dissertation, but it carries the via-collision pain documented in
      `../control-unit-kicad/CLAUDE.md` - read that first.
- [ ] Manufactured PCB layout (not started). Separate file from the perfboard.
      Board outline, placement, routing, DRC, then Gerbers.
- [x] ~~Decide 5V versus 12V encoder supply~~ - 5V committed 2026-08-28; 12V deferred
      to be designed alongside the Eurorack translation module's 24V rail.
- [ ] Firmware: quadrature decode on GP16/GP17, I2C target, IRQ on GP6.
