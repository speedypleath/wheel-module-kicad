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

### 3. `Device:CP` caches as an empty stub with zero pins - because it does not exist

`schematic_place_symbol` cached `Device:CP` (polarised capacitor) into `lib_symbols` as
`(symbol "Device:CP" (in_bom yes) (on_board yes) (symbol "CP_0_1"))` - **no pins at
all**. `schematic_get_pin_positions` returned an empty list, and the part would have
vanished from the netlist. `Device:C` caches correctly.

**Corrected 2026-09-03: the `extends` explanation below was wrong.** KiCad 10's
`Device.kicad_sym` has no `CP` symbol at all - the polarised capacitor is
**`Device:C_Polarized`** (`grep '(symbol "C' Device.kicad_sym`). `schematic_place_symbol`
does not fail on a name it cannot find; it writes a plausible-looking empty stub. So a
zero-pin cache usually means **the lib_id is wrong**, not that inheritance broke.
`Device:C_Polarized` caches correctly with both pins and is pin-identical to `Device:C`
(2 passive pins at `(0, +/-3.81)`, not an `extends` symbol), so it is a drop-in swap:
C1 was moved to it on 2026-09-03 with the wires, ERC and netlist all unchanged.

**After placing any symbol, audit the cached pin count.** Note the audit snippet below
must **bound the `lib_symbols` block** by paren-matching first - run it over the whole
file and the last cached symbol absorbs every `(pin "1" (uuid ...))` in the instance
bodies below it and reports a nonsense count (47 for a 2-pin capacitor):

```python
starts=[(m.start(),m.group(1)) for m in re.finditer(r'\(symbol "([A-Za-z_0-9]+:[^"]+)"',src)]
for i,(pos,name) in enumerate(starts):
    end = starts[i+1][0] if i+1<len(starts) else len(src)
    print(name, src[pos:end].count('(pin '))
```

At the time C1 was re-placed as `Device:C` (a 10uF ceramic, which avoided the polarity
question entirely). **Superseded 2026-09-03:** the owner's actual part is a 10uF 25V
D4x7 aluminium electrolytic, so C1 is now `Device:C_Polarized` with a `Voltage` field of
`25V`. Pin 1 was already `+5V` and pin 2 `GND` on all three boards, which is exactly the
polarised convention, so nothing had to be rotated or re-netted.

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

All **symbols** are stock KiCad 10. One **footprint** is vendored, as of 2026-09-03:
`libraries/wheel-module.pretty/CP_Radial_D4.0mm_P2.50mm.kicad_mod`, registered in
`project/fp-lib-table` as the `wheel-module` library via `${KIPRJMOD}/../libraries/`.
It is C1's D4x7 electrolytic, and it exists because **no stock `CP_Radial` pairs a 4 mm
can with a 2.50 mm pitch** - and 2.50 is the only pitch that keeps pads on the 2.54 mm
grid (2.00 would sit 0.54 mm off a hole, versus 0.04 mm for 2.50). It is generated, not
hand-written: derived from the stock `CP_Radial_D4.0mm_P2.00mm` by pushing pad 2 out to
2.5 mm and translating the can +0.25 mm so it stays centred between the leads. See the
footprint-derivation trap in the stripboard section before regenerating it.

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

`project/haptic-console-wheel-module-stripboard.kicad_pcb`, 40 x 40 holes,
104.14 mm square. A **third** build, separate from both the fabricated board and the
plain-perfboard one, for continuous-strip Veroboard. Build guide:
`docs/stripboard-wiring.md`, plus an interactive `docs/stripboard-wiring.html`.
Strips run horizontally on `B.Cu`, link wires on `F.Cu`.

**The grid is the stock, not the circuit.** It was resized from 28 x 30 to the real
40 x 40 board on 2026-08-30. Placement did not move - the circuit still sits in
cols 1-28 / rows 1-29 - but every strip now runs the full 40 columns, so the
right-hand end of a row is the same node as the part the circuit uses. Widening the
grid is therefore not cosmetic: it extends live copper past the last part. It was
safe here only because nothing else sits out there. Re-run the audit after any
resize; it is what proves no segment picked up a second net.

**The board is generated, not hand-built - rebuild it, don't patch it.**
`scripts/layout.py` is the source of truth (pure data, no `pcbnew`); the engine that
turns it into copper lives in the shared **`~/KiCad/kicad-stripboard`** repo, alongside
`jumper-wires-kicad`. To regenerate from the perfboard seed:

```bash
~/KiCad/kicad-stripboard/build.py scripts/layout.py \
    project/haptic-console-wheel-module-stripboard.kicad_pcb \
    --from project/haptic-console-wheel-module-perfboard.kicad_pcb
```

That reproduces the committed board exactly (same file size, zero diff once sorted -
only KiCad's internal emission order and UUIDs differ). The four stages run as separate
processes, and the last one is the strip audit, which fails the build. Every pcbnew
trap below is handled inside the engine; read `stripboard/kicad.py` before working
around any of them again.

**The HTML build guide is generated too.** `scripts/wiring_guide.py` renders
`docs/stripboard-wiring.html` from `scripts/layout.py` plus a read-back of the built
board - the strip table comes from the engine's own audit output and the placement
cards from a `pcbnew` pad dump, so the page cannot state a net the copper does not
carry. Re-run `python3 scripts/wiring_guide.py` after any rebuild. The Markdown
guide beside it is still hand-maintained; keep the two in step.

**The board map must draw each part's `*.Fab` body, never its courtyard.** It drew
the courtyard until 2026-08-30, and on the Pico that runs ~1.5 mm proud at each end -
enough to cover the whole neighbouring strip. The map showed the module sitting on
the `+5V` rail when in reality the body clears it by 0.42 mm, and the owner asked for
a layout change on the strength of it. A drawing that overstates a part's extent is
worse than no drawing. Two sub-traps in reading `*.Fab`: it also carries a `REF**`
`PCB_TEXT` (filter to `PCB_SHAPE`), and the Pico's USB shell is a `Polygon` there
that overhangs the module's top edge by 1.3 mm - skip polygons, they mark features,
not the outline, and that shell rides 8.5 mm up on the socket headers anyway.

**`PCB_SHAPE.GetBoundingBox()` returns a temporary you must not keep.** Holding one
and `Merge()`-ing the others into it returned a box at `x = -156.685` with zero
extent. Same SWIG lifetime family as the `FindNet` and post-`Remove()` flakiness
below. Read `GetLeft()/GetTop()/...` into plain ints inside the loop and min/max
those instead.

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
**Corollary: a rail with no pads on it cannot infer a net.** The old `+5V` rail was
reached only by link wires, so it silently landed on net 0 and every link touching it
read as a short; it needed an explicit `row_force_net` override. That rail is gone as
of 2026-08-30 and the override with it, but keep the rule in mind before adding one.

**`+5V` cannot have a full-width rail at all, and this is structural.** A strip that
spans the Pico is only safe on a row whose two pins are the same net, and the only
such rows are the three GND ones. So `+5V` lives on the right-hand segment of the
VSYS row (row 3), where `U1.39` and `C1.1` already sit and the net infers itself, and
the hub's 5 V is carried over the top of the module from `J1.3` by one long link.
That row's *left* segment carries Pico pin 2, GPIO1 - it must stay cut at column 12,
or 5 V lands on a GPIO.

**Do not put a via at a cut hole.** A spot-faced hole has no copper. A 2.54 mm gap
minus the 0.95 mm end cap on each strip leaves only 0.32 mm either side of a 1.5 mm
via - guaranteed shorts. Omit the via; the `B.SilkS` X marker documents the cut.

**Route link wires only along gutter lines** (half-pitch offsets between hole lines),
with 1.27 mm step-in segments. A link running down a hole column touches every via
it passes. Travelling *along* a strip's own row is fine - same net.

**Skip grid vias inside footprint courtyards**, or every hole under a component body
trips `pth_inside_courtyard`. They are hidden under the part anyway.

**The link wires are also drawn as physical jumper wires, on the SOLDER side.**
The `wires` stage places one decorative `JumperWires` footprint per link - no pads,
no net, so DRC is unaffected (still 0 errors, still exactly 240 warnings). Colours
follow the control unit's convention so a net is the same colour on every board:
red power, blue GND (the kit has no black), yellow I2C/IRQ, green `/LNK`.

They run on the **back** (`wire_side="back"`) because the component side is crowded -
the Pico spans twenty rows and `J1`/`J2`/the LEDs sit on the edges the long links
follow, so front-side wires lay across component bodies. This inverts the build
order: links go on **after** the parts, not before.

A wire is drawn straight between a link's **first and last** waypoint; the gutter
waypoints in between are a copper-routing device only, and an insulated wire may
pass over anything. The three GND spine taps carry `wire=False` - they are solder
joints on one continuous run, not wires of their own, which is why the file has 11
links but 8 wires. `${JUMPER_WIRES_LIB}` must be configured (Preferences > Configure
Paths) or the models silently fail to resolve.

**Swapping a footprint: take the library's text placement, not the old part's.**
Carrying the old reference/value positions across a swap put C1's `C1` label on the new
part's round silk outline and produced **34 `silk_overlap` errors** on the fabricated
board (which grades silk as an error via a local override). Read the replacement's own
`(property "Reference" (at ...))` offset out of the `.kicad_mod` and apply it relative to
the footprint origin.

**Deriving a footprint: the pads and the silk clearance notch move independently.**
`CP_Radial_D4.0mm_P2.50mm` was made from the stock `..._P2.00mm` by translating the body
+0.25 mm (keeping the can centred between the leads) and moving pad 2 +0.50 mm. But the
stock silk has a **notch cut around pad 2**, and that notch travelled with the body, so
it ended up 0.25 mm out of register and the hatching clipped the pad - 2
`silk_over_copper` apiece on the fab board and the stripboard. The generator now re-cuts
the notch around pad 2's final position (segment-to-point distance < pad radius +
0.25 mm, collected before any `Remove()`). Regenerate with
`scratchpad/mkfp.py`-style code rather than editing the `.kicad_mod`.

**An accurate body is worth drawing - the courtyard is load-bearing.** C1 was first
modelled with the stock 5 mm can as a stand-in. Its 5.4 mm courtyard overlapped U1 by
0.32 mm and swallowed the col-19 hole where the `+5V` link lands, which made the engine
skip that via and orphan the link (1 DRC error + 1 unconnected). That pushed C1 from
col 18 to col 21 - a layout change made entirely to accommodate a part 1 mm bigger than
the real one. The true D4 can has a 4.59 mm courtyard, clears U1 by 0.18 mm, and sits at
col 18 beside the Pico's VSYS pin where a bulk cap belongs. Same lesson as the `*.Fab`
board-map trap above: **a drawing that overstates a part's extent causes real, wrong
layout decisions.**

**Project-local footprint libraries need `footprint_libs`.** The engine resolved every
footprint as `{footprint_lib}/{libname}.pretty`, i.e. all under one stock root, so a
`wheel-module:` library was unloadable. `BoardSpec` now takes
`footprint_libs={libname: /abs/path.pretty}`, consulted by `spec.resolve_lib()` before
the root. That is a change to the **shared** `~/KiCad/kicad-stripboard` repo; it is
backwards compatible (empty dict = old behaviour) but the other board projects share it.

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

**The module-level footprint-library wrappers are dead here.** `pcbnew.FootprintSave`
and `pcbnew.FootprintLibCreate` both dereference a module-global `plug` that is `None`
(`AttributeError: 'NoneType' object has no attribute 'FootprintSave'`) - the same SWIG
plugin flakiness as `FindNet`. Get a real one with
`pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)`, which has a working
`FootprintSave`. Its `CreateLibrary` is **not** exposed to Python (and the SWIG
`FootprintLibCreate` shim just calls it), but a `.pretty` is only a directory of
`.kicad_mod` files - `os.makedirs` it yourself, then `io.FootprintSave(dir, fp)`.
Note also `FOOTPRINT.SetDescription` does not exist; it is `SetLibDescription`.

**A stage that mutates the board segfaults on exit, after saving successfully.**
pcbnew's SWIG objects have no destructors (`no destructor found` on stderr), and
CPython's interpreter teardown then crashes - exit status -11 on a build whose
`SaveBoard` had already worked. Leave with `os._exit(rc)` after flushing, or every
successful build reports failure.

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
      build (1331 grid holes at 40 x 40, netted to the strip they sit on). The plain-perfboard
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
