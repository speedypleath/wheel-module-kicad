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

**Amendment, 2026-08-28 — `pcbnew` scripting is allowed on `.kicad_pcb`, text editing
still is not.** The fabricated board's 38 traces and its GND pour were created by
scripting KiCad's own bundled `pcbnew` Python module
(`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3`),
not by editing the S-expression. This is the same distinction `../control-unit-kicad/CLAUDE.md`
draws: `pcbnew` goes through KiCad's real object model and writer, so it cannot desync
pin or property data the way regex munging can. It was forced here — the MCP
`pcb_add_zone` tool actively destroys routing (see the fabricated-PCB section below) and
`pcb_autoroute` produces shorts. Prefer MCP tools for placement, which they handle well;
use `pcbnew` for traces and zones. Always re-run `kicad-cli pcb drc` afterwards. Raw text
edits to `.kicad_pcb` remain banned.

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

## Fabricated PCB layout (2026-08-28 session)

`project/haptic-console-wheel-module.kicad_pcb`, 68 x 58 mm, 2-layer, all through-hole.
Separate file from the perfboard. Five traps here, all of them expensive.

**Get pad coordinates from `pcbnew`, never from a regex over the S-expression.** A
hand-rolled parser reported R1 at y=43.18 and R5 at y=48.26; `pcbnew` (and DRC) put
them the other way round. Routing was done against the wrong numbers and produced six
net shorts. The parser agreed with what had been *intended*, which is exactly what
makes this failure mode dangerous — it looks like confirmation. Dump pads with
`fp.Pads()` / `p.GetPosition()` and treat that as the only truth.

**The MCP `pcb_add_zone` tool is not usable on this KiCad.** It returns a plausible
UUID, but `pcbnew` then reports `GetAreaCount() == 0` — no zone was really created.
Worse, writing the file **silently dropped all 38 routed segments**. Build zones through
`pcbnew` instead. Note `ZONE.AddPolygon()` accepts only a `SHAPE_LINE_CHAIN` in practice,
even though the SWIG error lists a `std::vector<VECTOR2I>` overload too; a Python list of
`VECTOR2I` fails. Fill with `pcbnew.ZONE_FILLER(board).Fill(board.Zones())`.

**`pcb_autoroute` is worse than not routing.** `strategy="freerouting"` fails outright
(the server looks for the `pcbnew` module and only recognises KiCad 8, though KiCad 10's
bundled Python has it). It silently falls back to `strategy="simple"`, which does
L-shaped routing with **no collision avoidance at all**: 32 traces produced 20 crossing
tracks, 12 shorts, 24 co-located holes and 14 dangling vias. Route by hand.

**`pcbnew.FindNet(name)` is unreliable here** — it sometimes returns a bare
`SwigPyObject` with no `GetNetCode`. It worked in one run and failed in the next on the
same file. Build a netname → netcode map from pads instead:
`codes[p.GetNetname()] = p.GetNetCode()`.

**GND needs no traces.** All 14 GND pads are through-hole, so a filled `B.Cu` pour
connects them all. That removes 14 of 32 connections before routing starts, and is what
makes hand-routing this board tractable.

**Routing constraints worth remembering.** The Pico's pad rows are on 2.54 mm pitch with
1.6 mm pads, so any track crossing under it must thread a 0.94 mm gap — avoid it; go
around the bottom (y=56.5) instead, which is also clear of the footprint's
`Antenna Copper Keep Out` zone (tracks not allowed, y 46.21-55.21). The Pico courtyard
reaches x=44.43, well past its x=41.78 pad column, so right-side parts need to start at
x>=46.5.

## Stripboard / Veroboard layout (2026-08-28 session)

`project/haptic-console-wheel-module-stripboard.kicad_pcb`, 28 x 30 holes,
73.66 x 78.74 mm. A **third** build, separate from both the fabricated board and the
plain-perfboard one, for continuous-strip Veroboard. Build guide:
`docs/stripboard-wiring.md`. Strips run horizontally on `B.Cu`, link wires on `F.Cu`.

**The rule that drives the whole layout: a strip is shared by every hole in its
row, including holes under pins nobody wired.** The question is never "did I connect
the right pads" but "does anything else sit on this strip". Two live instances here:

- **Row offset 7 from Pico pin 1 must be cut.** Pico pin 8 (GND) is on the left of
  that row and **pin 33 (AGND)** on the right. Leaving it whole ties AGND to GND and
  re-creates the `power_out`/`power_out` ERC violation documented above.
- **Row offsets 2, 12 and 17 must NOT be cut** - they carry GND on *both* sides
  (pins 3/38, 13/28, 18/23), so leaving them whole buys six GND connections and the
  GND bus for free. Getting this backwards is easy and costs either a short or a
  dozen needless link wires.

`J1` pin 2 (hub 3.3V) is the same class of trap: placed flush beside the Pico it
lands on the `/LNK` strip, breaking the "stays unconnected" invariant. Cut column 5
isolates it.

**Derive every strip's net from the pads on it, never from intent** - and treat a
segment carrying two nets as a hard error that aborts the write. That check is what
makes this layout trustworthy; it caught a stale-placement run immediately.
**Corollary: a rail with no pads on it cannot infer a net.** Row 2 (+5V) is reached
only by link wires, so it silently landed on net 0 and every link touching it read as
a short. Rails like that need an explicit net override.

**Do not put a via at a cut hole.** A spot-faced hole has no copper. A 2.54 mm gap
minus the 0.95 mm end cap on each strip leaves only 0.32 mm either side of a 1.5 mm
via - guaranteed shorts. Omit the via; the `B.SilkS` X marker documents the cut.

**Route link wires only along gutter lines** (half-pitch offsets between hole lines),
with 1.27 mm step-in segments. A link running down a hole column touches every via
it passes. Travelling *along* a strip's own row is fine - same net.

**Skip grid vias inside footprint courtyards**, or every hole under a component body
trips `pth_inside_courtyard`. They are hidden under the part anyway.

### pcbnew traps hit this session

**This pcbnew's SWIG proxies degrade after the first `board.Remove()`** - and it
poisons *unrelated* objects, not just the removed one. After removing a `PCB_SHAPE`,
`FindFootprintByReference` started returning bare `SwigPyObject`, and the footprint
plugin behind `pcbnew.FootprintLoad` lost its methods. Same family as the `FindNet`
flakiness above. Two defences: do **every** lookup and library load *before* the first
removal, and keep **one kind of mutation per process run** (this build is three
scripts: place / keepout / copper).

**`footprint.Remove(zone)` corrupts the board badly enough that `SaveBoard` writes a
zero-byte file.** Hit while trying to delete the Pico's `Antenna Copper Keep Out`
(which forbids tracks between the pin rows - unhonourable on Veroboard, where the
strips run under the module by construction, and pointless here since this is a
non-W Pico with no radio). **Disable the rule area instead**:
`SetDoNotAllowTracks(False)` and friends. It leaves the zone in place as
documentation and saves correctly.

**The stackup API is not usable from Python here.** `GetStackupDescriptor()` returns
a bare `SwigPyObject` with no `GetCount`, and there is no `Cast_to_BOARD_STACKUP`.
The control unit's tan-Veroboard colour therefore cannot be applied by script, and
raw text edits stay banned - so it is a GUI job (Board Setup > Physical Stackup).
Renders are green FR4 until then.

**Expected DRC result: 0 errors, 0 unconnected pads, and ~240 warnings.** The
warnings are `via_dangling`/`track_dangling` plus three pre-existing
`lib_footprint_mismatch` inherited from the perfboard file. Dangling is inherent to
modelling perfboard holes as vias - every hole touches only the strip on the back -
and bare strips really are unconnected copper on a stripboard. This is the
stripboard equivalent of "32 unconnected pads is the correct result". **Check errors
with `--severity-error`; do not chase the warnings.**

## MCP server scope (2026-08-28)

The `kicad-seeed` / `kicad-namelessdrake` servers were registered in `~/.claude.json`
at **local (per-project) scope**, attached only to `control-unit-kicad` and
`pneumatic-module-kicad`. Local scope does not inherit across sibling directories, so
a session started in `wheel-module-kicad` got none of them and had to do everything
through `pcbnew`. If they go missing again, re-add at **user** scope
(`claude mcp add-json --scope user ...`) rather than per project.

## TODO

- [ ] Cosmetic pass in the GUI: auto-placed reference/value text overlaps net labels
      around J1, J2, R1-R3 and the LEDs. Same issue on the perfboard silkscreen
      (D2's reference sits under J1's outline) - three `silk_overlap` warnings.
- [x] ~~Perfboard hole grid / render trick~~ - done 2026-08-28 for the **stripboard**
      build (571 grid holes, netted to the strip they sit on). The plain-perfboard
      file still has no hole grid; add it the same way if that render is needed.
- [ ] Tan Veroboard stackup on the stripboard render: blocked from Python (see the
      stripboard section). Do it in the GUI - Board Setup > Physical Stackup,
      dielectric `#9E683EFF` Phenolic FR2 1.51mm, both masks `#9E683E00`,
      copper finish None - then re-render.
- [x] ~~Manufactured PCB layout~~ - done 2026-08-28. 68 x 58 mm 2-layer, 38 segments
      plus a filled `B.Cu` GND pour, 0 DRC errors / 0 unconnected. Gerbers exported.
- [ ] Mounting holes are **not** on the fabricated board yet. Decide the M3 chassis
      fixing pattern first, then add them.
- [x] ~~Decide 5V versus 12V encoder supply~~ - 5V committed 2026-08-28; 12V deferred
      to be designed alongside the Eurorack translation module's 24V rail.
- [ ] Firmware: quadrature decode on GP16/GP17, I2C target, IRQ on GP6.
