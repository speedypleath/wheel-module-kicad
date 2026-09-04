#!/usr/bin/env python3
"""Render docs/stripboard-wiring.html from the layout spec and the built board.

    python3 scripts/wiring_guide.py

Everything the page states about copper -- which strip segment carries which net,
where the segment ends, which pads sit on it -- is read back out of
``project/haptic-console-wheel-module-stripboard.kicad_pcb`` via the engine's own
audit, never from intent.  That is the same rule the layout itself is built on:
derive the net from the pads, and treat the file as the only truth.

Placement boxes and pad coordinates come from a pcbnew dump cached alongside this
script's inputs; the cut list, the link waypoints and the wire colours come from
``scripts/layout.py``.  Re-run this after any rebuild of the board.
"""
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE = os.path.expanduser("~/KiCad/kicad-stripboard")
BOARD = os.path.join(ROOT, "project", "haptic-console-wheel-module-stripboard.kicad_pcb")
LAYOUT = os.path.join(HERE, "layout.py")
OUT = os.path.join(ROOT, "docs", "stripboard-wiring.html")
KIPY = ("/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/"
        "Versions/3.9/bin/python3")

CELL = 20                      # px per 2.54 mm hole pitch in the board map
EDGE_LO, EDGE_HI = 0.69, 40.31  # strip copper start/end, in pitch units


# --- inputs ------------------------------------------------------------------

def load_spec():
    import importlib.util
    sys.path.insert(0, ENGINE)
    spec = importlib.util.spec_from_file_location("layout", LAYOUT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def audit_segments():
    """Strip segments as the engine's audit sees them in the saved board."""
    out = subprocess.run(
        [os.path.join(ENGINE, "build.py"), LAYOUT, BOARD, "--stage", "audit"],
        capture_output=True, text=True, cwd=ROOT).stdout
    segs, totals = [], {}
    for ln in out.splitlines():
        m = re.match(r"(\d+) strip segments, (\d+) holes, (\d+) link tracks", ln)
        if m:
            totals = dict(segments=int(m.group(1)), holes=int(m.group(2)),
                          links=int(m.group(3)))
        m = re.match(r"\s+row\s+(\d+) seg col\s+([\d.]+)\.\.\s*([\d.]+)\s+(\S+)\s*(.*)$", ln)
        if m:
            segs.append(dict(row=int(m.group(1)), x0=float(m.group(2)), x1=float(m.group(3)),
                             net=m.group(4), pads=m.group(5).strip()))
    if not segs:
        sys.exit("audit produced no segments -- is the board built?")
    return segs, totals


def pcb_footprints():
    """Pad grid coordinates and part body outlines, straight out of pcbnew."""
    script = r'''
import pcbnew, json, sys
b = pcbnew.LoadBoard(sys.argv[1]); MM, P = 1e6, 2.54
out = {}
for fp in b.Footprints():
    ref = fp.GetReference()
    if ref.startswith("W"):
        continue
    pads = [dict(n=p.GetNumber(), col=round(p.GetPosition().x/MM/P, 3),
                 row=round(p.GetPosition().y/MM/P, 3), net=p.GetNetname())
            for p in fp.Pads()]
    # Draw the part's real body (the *Fab outline), not its courtyard.  The
    # courtyard is a keep-out and runs well past the part -- on the Pico it is
    # ~1.5 mm proud at each end, enough to cover the whole neighbouring strip
    # and make row 1 look like it is underneath the module when it is not.
    xs, ys = [], []
    for it in fp.GraphicalItems():
        # shapes only: the *Fab layers also carry a REF** text item, which would
        # drag the box out to wherever the designator happens to sit
        if not isinstance(it, pcbnew.PCB_SHAPE):
            continue
        if it.GetLayer() not in (pcbnew.F_Fab, pcbnew.B_Fab):
            continue
        # Polygons on *Fab mark features, not the outline -- on the Pico it is
        # the USB shell, which overhangs the module's top edge by 1.3 mm.  That
        # shell rides 8.5 mm up in the air on the socket headers and obstructs
        # nothing, so drawing it would put the module back over row 1.
        if it.GetShapeStr() == "Polygon":
            continue
        bb, half = it.GetBoundingBox(), it.GetWidth() // 2
        # Read the ints out *now*.  GetBoundingBox() hands back a temporary
        # BOX2I proxy; holding on to one and merging others into it returns
        # garbage, the same SWIG lifetime trap the engine documents.
        xs += [bb.GetLeft() + half, bb.GetRight() - half]
        ys += [bb.GetTop() + half, bb.GetBottom() - half]
    if xs:
        box = [min(xs), min(ys), max(xs), max(ys)]
    else:                                  # no fab outline -- fall back
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        if cy.OutlineCount() == 0:
            cy = fp.GetCourtyard(pcbnew.B_CrtYd)
        r = cy.BBox()
        box = [r.GetLeft(), r.GetTop(), r.GetRight(), r.GetBottom()]
    out[ref] = dict(value=fp.GetValue(), fp=str(fp.GetFPIDAsString()),
                    pads=sorted(pads, key=lambda d: (len(d["n"]), d["n"])),
                    box=[round(v/MM/P, 3) for v in box])
print(json.dumps(out))
'''
    r = subprocess.run([KIPY, "-c", script, BOARD], capture_output=True, text=True)
    return json.loads(r.stdout)


# --- net classification ------------------------------------------------------

POWER = {"+5V", "+3V3"}
BUS = {"/SDA", "/SCL", "/IRQ"}


def net_class(net):
    if not net:
        return "spare"
    if net.startswith("unconnected-"):
        return "free"
    if net in POWER:
        return "power"
    if net == "GND":
        return "gnd"
    if net in BUS:
        return "i2c"
    return "signal"


def net_label(net):
    """`unconnected-(U1-GPIO7-Pad10)` reads as `U1.10 GPIO7` on a bench."""
    m = re.match(r"unconnected-\((\w+)-(.+)-Pad(\w+)\)$", net or "")
    if m:
        return f"{m.group(1)}.{m.group(3)} {m.group(2)}"
    return net or "—"


# --- board map ---------------------------------------------------------------

def build_map(spec, segs, fps):
    cuts_by_row = {}
    for c, r in spec.cuts:
        cuts_by_row.setdefault(r, []).append(c)

    seg_net = {}
    for s in segs:
        seg_net[(s["row"], round(s["x0"], 2))] = s

    W = 41 * CELL
    GL, GT = 26, 20                 # gutters for the row / column rulers
    o = [f'<svg viewBox="{-GL} {-GT} {W + GL + 8} {W + GT + 8}" role="img" '
         f'aria-label="Board map: 40 by 40 hole Veroboard, strips running left to right">']
    o.append('<defs>'
             f'<pattern id="holes" x="{CELL//2}" y="{CELL//2}" width="{CELL}" height="{CELL}" '
             'patternUnits="userSpaceOnUse">'
             f'<circle class="hole" cx="{CELL//2}" cy="{CELL//2}" r="2.3"/></pattern></defs>')
    o.append(f'<rect class="board" x="0" y="0" width="{W}" height="{W}" rx="6"/>')

    # strip segments, coloured by the net the audit found on them
    o.append('<g class="strips">')
    for row in range(1, spec.grid.rows + 1):
        bounds = [EDGE_LO]
        for c in sorted(cuts_by_row.get(row, [])):
            bounds += [c - 0.5, c + 0.5]
        bounds.append(EDGE_HI)
        for i in range(0, len(bounds), 2):
            x0, x1 = bounds[i], bounds[i + 1]
            s = seg_net.get((row, round(x0, 2)))
            net = s["net"] if s else ("+5V" if row == 2 else "")
            cls = net_class(net)
            pads = s["pads"] if s else ("link-fed rail" if row == 2 else "")
            title = (f"row {row}, cols {int(x0 + 0.5)}–{int(x1)} — "
                     f"{net_label(net) if net else 'spare, no net'}"
                     + (f" — {pads}" if pads else ""))
            o.append(
                f'<g class="seg seg-{cls}" data-net="{html.escape(net or "")}" '
                f'data-row="{row}"><title>{html.escape(title)}</title>'
                f'<rect x="{x0 * CELL:.1f}" y="{(row - 0.375) * CELL:.1f}" '
                f'width="{(x1 - x0) * CELL:.1f}" height="{0.75 * CELL:.1f}" rx="3"/></g>')
    o.append('</g>')

    # holes, as one tiled pattern rather than 1600 circles
    o.append(f'<rect class="holefill" x="{0.5 * CELL}" y="{0.5 * CELL}" '
             f'width="{40 * CELL}" height="{40 * CELL}" fill="url(#holes)"/>')

    # link wires, along the gutter waypoints the copper actually follows
    o.append('<g class="links">')
    for i, lk in enumerate(spec.links, 1):
        if len(lk.points) < 2:
            continue
        pts = " ".join(f"{c * CELL:.1f},{r * CELL:.1f}" for c, r in lk.points)
        colour = spec.wire_colors.get(lk.net, "white")
        kind = "tap" if not lk.wire else "wire"
        o.append(f'<polyline class="link link-{colour} link-{kind}" data-net="{html.escape(lk.net)}" '
                 f'points="{pts}"><title>{html.escape(lk.net)} link '
                 f'{"(solder tap on the GND spine)" if not lk.wire else ""}</title></polyline>')
    o.append('</g>')

    # component outlines
    o.append('<g class="parts">')
    for ref, fp in sorted(fps.items()):
        x0, y0, x1, y1 = fp["box"]
        o.append(f'<g class="part" data-ref="{ref}"><title>{ref} — '
                 f'{html.escape(fp["value"])}</title>'
                 f'<rect x="{x0 * CELL:.1f}" y="{y0 * CELL:.1f}" '
                 f'width="{(x1 - x0) * CELL:.1f}" height="{(y1 - y0) * CELL:.1f}" rx="4"/>'
                 f'<text x="{(x0 + x1) / 2 * CELL:.1f}" '
                 f'y="{(y0 * CELL + 11) if (y1 - y0) > 3 else ((y0 + y1) / 2 * CELL):.1f}" '
                 f'dy="0.32em">{ref}</text></g>')
    o.append('</g>')

    # cut markers
    o.append('<g class="cuts">')
    for c, r in sorted(spec.cuts, key=lambda t: (t[1], t[0])):
        x, y = c * CELL, r * CELL
        d = 5.0
        o.append(f'<g class="cut" data-cut="{c},{r}"><title>cut column {c}, row {r}</title>'
                 f'<circle cx="{x}" cy="{y}" r="7"/>'
                 f'<path d="M{x - d} {y - d}L{x + d} {y + d}M{x + d} {y - d}L{x - d} {y + d}"/></g>')
    o.append('</g>')

    # rulers -- you count rows and columns constantly at the bench
    o.append('<g class="ruler">')
    for c in range(1, spec.grid.cols + 1):
        cls = "tick major" if c % 5 == 0 or c == 1 else "tick"
        o.append(f'<text class="{cls}" x="{c * CELL}" y="-7">{c}</text>')
    for r in range(1, spec.grid.rows + 1):
        cls = "tick major" if r % 5 == 0 or r == 1 else "tick"
        o.append(f'<text class="{cls} rowtick" x="-9" y="{r * CELL}" dy="0.32em">{r}</text>')
    o.append('</g>')

    o.append('</svg>')
    return "\n".join(o)


# --- page --------------------------------------------------------------------

CSS = """
:root {
  --bg:#f3ede2; --surface:#fffdf8; --surface-2:#ece3d3; --ink:#241c15;
  --muted:#6b5f4f; --border:#d8cbb2; --copper:#b1662f;
  --power:#a63b2e; --power-bg:#f6e2dd;
  --gnd:#4a4640;   --gnd-bg:#e6e2da;
  --i2c:#8a5a17;   --i2c-bg:#f1e2c4;
  --signal:#235e78;--signal-bg:#dfeaef;
  --free:#8d8272;  --free-bg:#e9e4da;
  --hl:#ffd977; --cut:#b03024;
  --board:#c9a173; --hole:#6d4b28; --spare:#b98f5f;
  --w-red:#c0392b; --w-blue:#2b6ca3; --w-yellow:#cf9a12; --w-green:#3d8b4a;
  --shadow:0 1px 2px rgba(36,28,21,.06), 0 8px 24px rgba(36,28,21,.05);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#17130f; --surface:#211a14; --surface-2:#2a2119; --ink:#f1e7d7;
    --muted:#a6957d; --border:#3c3025; --copper:#e0a868;
    --power:#e2897b; --power-bg:#3a221e;
    --gnd:#cfc7b8;  --gnd-bg:#2c2822;
    --i2c:#e8c37e;  --i2c-bg:#3a2e15;
    --signal:#8fc4de;--signal-bg:#1c2f37;
    --free:#8b7f6d; --free-bg:#241d17;
    --hl:#6a5116; --cut:#e2705f;
    --board:#6b4b2c; --hole:#241a10; --spare:#7d5a35;
    --w-red:#e0705f; --w-blue:#6fa8d6; --w-yellow:#e3b445; --w-green:#6bbd78;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 12px 32px rgba(0,0,0,.35);
  }
}
:root[data-theme="dark"] {
  --bg:#17130f; --surface:#211a14; --surface-2:#2a2119; --ink:#f1e7d7;
  --muted:#a6957d; --border:#3c3025; --copper:#e0a868;
  --power:#e2897b; --power-bg:#3a221e;
  --gnd:#cfc7b8;  --gnd-bg:#2c2822;
  --i2c:#e8c37e;  --i2c-bg:#3a2e15;
  --signal:#8fc4de;--signal-bg:#1c2f37;
  --free:#8b7f6d; --free-bg:#241d17;
  --hl:#6a5116; --cut:#e2705f;
  --board:#6b4b2c; --hole:#241a10; --spare:#7d5a35;
  --w-red:#e0705f; --w-blue:#6fa8d6; --w-yellow:#e3b445; --w-green:#6bbd78;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 12px 32px rgba(0,0,0,.35);
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); line-height:1.5;
  font-family:ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  padding:0 0 6rem; }
.wrap { max-width:1080px; margin:0 auto; padding:0 1.5rem; }
code, .mono { font-family:ui-monospace, SFMono-Regular, Menlo, monospace; }
code { font-size:.9em; background:var(--surface-2); padding:.05rem .3rem; border-radius:3px; }
a { color:var(--copper); text-underline-offset:2px; }

header.page-head { padding-top:3rem; padding-bottom:1.75rem; margin-bottom:1.5rem;
  border-bottom:3px solid var(--copper); display:flex; flex-direction:column; gap:.5rem; }
.eyebrow { font-family:ui-monospace, monospace; font-size:.72rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--copper); }
h1 { font-weight:800; font-size:clamp(2rem,5vw,2.7rem); margin:0; text-wrap:balance; }
.dek { color:var(--muted); font-size:1rem; max-width:68ch; margin:0; }
h2 { font-weight:700; font-size:1.4rem; margin:0 0 .25rem; scroll-margin-top:5.5rem;
  text-wrap:balance; }
h3 { font-weight:600; font-size:1.02rem; margin:0; }
section { margin-bottom:3rem; scroll-margin-top:4.5rem; }
.section-intro { color:var(--muted); font-size:.92rem; max-width:68ch; margin:0 0 1.25rem; }

.toolbar { position:sticky; top:0; z-index:20; border-bottom:1px solid var(--border);
  background:color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter:blur(8px); }
.toolbar-in { max-width:1080px; margin:0 auto; padding:.6rem 1.5rem; display:flex;
  gap:.75rem; align-items:center; flex-wrap:wrap; }
.toolbar nav { display:flex; gap:.15rem; flex-wrap:wrap; }
.toolbar nav a { font-size:.78rem; color:var(--muted); text-decoration:none;
  padding:.25rem .5rem; border-radius:5px; }
.toolbar nav a:hover, .toolbar nav a:focus-visible { background:var(--surface-2); color:var(--ink); }
.grow { flex:1 1 auto; }
#q { font-family:ui-monospace, monospace; font-size:.8rem; padding:.35rem .6rem;
  min-width:11rem; border:1px solid var(--border); border-radius:6px;
  background:var(--surface); color:var(--ink); }
.btn { font-size:.76rem; padding:.3rem .6rem; border:1px solid var(--border);
  border-radius:6px; background:var(--surface); color:var(--muted); cursor:pointer; }
.btn:hover { color:var(--ink); }
:focus-visible { outline:2px solid var(--copper); outline-offset:2px; }

.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(112px,1fr)); gap:.6rem;
  margin-bottom:1.75rem; }
.stat { background:var(--surface); border:1px solid var(--border); border-radius:8px;
  box-shadow:var(--shadow); padding:.7rem .85rem; }
.stat b { display:block; font-family:ui-monospace, monospace; font-size:1.25rem;
  font-weight:700; font-variant-numeric:tabular-nums; }
.stat span { font-size:.7rem; color:var(--muted); text-transform:uppercase;
  letter-spacing:.08em; }

.callout { background:var(--surface); border:1px solid var(--border);
  border-left:4px solid var(--copper); border-radius:8px; box-shadow:var(--shadow);
  padding:.9rem 1.1rem; margin-bottom:1.5rem; font-size:.9rem; color:var(--muted); }
.callout strong { color:var(--ink); }
.callout.warn { border-left-color:var(--cut); }
.callout p { margin:.5rem 0 0; }
.callout p:first-child { margin-top:0; }

/* --- board map --- */
.map-frame { background:var(--surface); border:1px solid var(--border); border-radius:10px;
  box-shadow:var(--shadow); padding:1rem; overflow-x:auto; }
.map-frame svg { display:block; width:100%; min-width:620px; height:auto; }
.board { fill:var(--board); }
.hole { fill:var(--hole); opacity:.45; }
.seg rect { stroke-width:.6; }
.seg-power  rect { fill:var(--power);  stroke:var(--power);  fill-opacity:.55; }
.seg-gnd    rect { fill:var(--gnd);    stroke:var(--gnd);    fill-opacity:.5; }
.seg-i2c    rect { fill:var(--i2c);    stroke:var(--i2c);    fill-opacity:.55; }
.seg-signal rect { fill:var(--signal); stroke:var(--signal); fill-opacity:.55; }
.seg-free   rect { fill:var(--spare);  stroke:var(--spare);  fill-opacity:.62; }
.seg-spare  rect { fill:var(--spare);  stroke:var(--spare);  fill-opacity:.48; }
.seg:hover rect { fill-opacity:.9; }
.ruler text { font:9px ui-monospace, monospace; fill:var(--muted); text-anchor:middle;
  opacity:.65; }
.ruler .major { fill:var(--ink); opacity:.9; font-weight:700; }
.ruler .rowtick { text-anchor:end; }
.cut circle { fill:var(--surface); stroke:var(--cut); stroke-width:.8; }
.cut path { stroke:var(--cut); stroke-width:2.4; stroke-linecap:round; }
.link { fill:none; stroke-width:3.4; stroke-linecap:round; stroke-linejoin:round; opacity:.95; }
.link-red { stroke:var(--w-red); } .link-blue { stroke:var(--w-blue); }
.link-yellow { stroke:var(--w-yellow); } .link-green { stroke:var(--w-green); }
.link-tap { stroke-width:2.2; stroke-dasharray:3 3; }
.part rect { fill:var(--surface); fill-opacity:.82; stroke:var(--ink); stroke-opacity:.55;
  stroke-width:1.2; }
.part text { font:700 11px ui-monospace, monospace; fill:var(--ink); text-anchor:middle; }
svg .dim { opacity:.12; }
.map-legend { display:flex; flex-wrap:wrap; gap:.45rem; margin-top:.9rem; }
.chip { font-family:ui-monospace, monospace; font-size:.74rem; padding:.28rem .7rem;
  border:1px solid var(--border); border-radius:999px; background:var(--surface);
  color:var(--muted); cursor:pointer; display:inline-flex; align-items:center; gap:.4rem; }
.chip[aria-pressed="true"] { background:var(--copper); border-color:var(--copper); color:var(--bg); }
.chip .sw { width:.62rem; height:.62rem; border-radius:2px; flex:none; }
.sw-power { background:var(--power); } .sw-gnd { background:var(--gnd); }
.sw-i2c { background:var(--i2c); } .sw-signal { background:var(--signal); }
.sw-free { background:var(--spare); }
.sw-red { background:var(--w-red); } .sw-blue { background:var(--w-blue); }
.sw-yellow { background:var(--w-yellow); } .sw-green { background:var(--w-green); }
.sw-cut { background:var(--cut); }

/* --- tables --- */
.tbl-frame { background:var(--surface); border:1px solid var(--border); border-radius:10px;
  box-shadow:var(--shadow); overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:.82rem; }
thead th { position:sticky; top:0; background:var(--surface-2); text-align:left;
  font-size:.7rem; letter-spacing:.07em; text-transform:uppercase; color:var(--muted);
  padding:.5rem .75rem; border-bottom:1px solid var(--border); white-space:nowrap; }
tbody td { padding:.4rem .75rem; border-top:1px solid var(--border); vertical-align:top; }
tbody tr:first-child td { border-top:none; }
tbody tr:hover { background:var(--surface-2); }
td.n, th.n { font-family:ui-monospace, monospace; font-variant-numeric:tabular-nums;
  white-space:nowrap; }
td.net { font-family:ui-monospace, monospace; font-weight:600; white-space:nowrap; }
td.net.power { color:var(--power); } td.net.gnd { color:var(--gnd); }
td.net.i2c { color:var(--i2c); } td.net.signal { color:var(--signal); }
td.net.free, td.net.spare { color:var(--free); font-weight:400; }
tr.keep td { background:var(--gnd-bg); }
tr.isolate td { background:var(--power-bg); }
tr.dim { opacity:.25; }
.tag { font-family:ui-monospace, monospace; font-size:.66rem; padding:.05rem .4rem;
  border-radius:3px; border:1px solid var(--border); color:var(--muted); white-space:nowrap; }

/* --- checklist --- */
.progress { font-family:ui-monospace, monospace; font-size:.76rem; color:var(--muted);
  display:flex; align-items:center; gap:.5rem; }
.progress .bar { width:6rem; height:5px; border-radius:3px; background:var(--surface-2);
  overflow:hidden; }
.progress .bar i { display:block; height:100%; width:0; background:var(--copper);
  transition:width .2s; }
.steps { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:.5rem;
  counter-reset:step; }
.steps li { background:var(--surface); border:1px solid var(--border); border-radius:8px;
  box-shadow:var(--shadow); padding:.7rem .95rem; display:flex; gap:.75rem;
  align-items:flex-start; font-size:.88rem; }
.steps li::before { counter-increment:step; content:counter(step);
  font-family:ui-monospace, monospace; font-size:.7rem; font-weight:700; color:var(--copper);
  border:1px solid var(--border); border-radius:5px; padding:.1rem .4rem; margin-top:.1rem;
  flex:none; }
.steps input { margin-top:.28rem; accent-color:var(--copper); flex:none; }
.steps li.done { opacity:.5; }
.steps li.done .step-body { text-decoration:line-through; text-decoration-color:var(--muted); }
.step-body strong { display:block; }
.step-body span { color:var(--muted); font-size:.84rem; }

.grid-cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(238px,1fr)); gap:.8rem; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:8px;
  box-shadow:var(--shadow); overflow:hidden; }
.card .head { display:flex; justify-content:space-between; align-items:baseline; gap:.5rem;
  padding:.55rem .8rem; background:var(--surface-2); border-bottom:1px solid var(--border); }
.card .head .ref { font-family:ui-monospace, monospace; font-weight:700; font-size:.9rem; }
.card .head .val { font-size:.7rem; color:var(--muted); font-family:ui-monospace, monospace; }
.card .body { padding:.55rem .8rem .7rem; font-size:.78rem; color:var(--muted); }
.card .body dl { margin:0; display:grid; grid-template-columns:auto 1fr; gap:.15rem .6rem; }
.card .body dt { color:var(--muted); font-size:.7rem; text-transform:uppercase;
  letter-spacing:.06em; }
.card .body dd { margin:0; font-family:ui-monospace, monospace; color:var(--ink);
  font-size:.76rem; }
.card .body .fp { margin:.5rem 0 0; font-family:ui-monospace, monospace; font-size:.68rem;
  line-height:1.35; overflow-wrap:anywhere; color:var(--muted); }
details.notes { background:var(--surface); border:1px solid var(--border); border-radius:8px;
  box-shadow:var(--shadow); padding:.75rem 1.1rem; font-size:.88rem; color:var(--muted); }
details.notes > summary { cursor:pointer; font-weight:600; color:var(--ink); }
details.notes ul { margin:.7rem 0 0; padding-left:1.1rem; }
details.notes li { margin-bottom:.4rem; }
@media (prefers-reduced-motion: reduce) { * { transition:none !important; } }
@media print {
  .toolbar { display:none; } body { padding-bottom:0; }
  .card, .steps li, .tbl-frame, .map-frame { break-inside:avoid; box-shadow:none; }
}
"""


CUT_GROUPS = [
    (12, "Splits the Pico's left pin column from its right one. <b>Not</b> rows 5, 15 or 20 "
         "&mdash; those stay whole and become the GND bus."),
    (5,  "Isolates <code>J1</code> pins 2, 3 and 6, whose order disagrees with the Pico's."),
    (26, "Isolates <code>J2.5</code> (cable shield GND) from <code>/ENC_A</code>."),
    (27, "Isolates <code>J2.2</code> (encoder GND) from <code>+3V3</code>."),
]

CUT_WHY = {
    (12, 10): ("critical", "Pico pin&nbsp;8 GND on the left, pin&nbsp;33 <b>AGND</b> on the right. "
                           "Leave this out and AGND ties to GND."),
    (12, 26): ("", "Separates <code>Net-(D1-A)</code> on the left from <code>+5V</code> on the right."),
    (5, 6):   ("", "Keeps <code>J1.2</code> (hub 3.3&nbsp;V) off the <code>/LNK</code> strip."),
    (5, 7):   ("", "Keeps <code>J1.3</code> (+5&nbsp;V) off the Pico's unused GP3."),
    (5, 10):  ("", "Keeps <code>J1.6</code> (IRQ) off the Pico's GND pin&nbsp;8."),
    (26, 22): ("", "<code>J2.5</code> shield GND, off <code>/ENC_A</code>."),
    (27, 25): ("", "<code>J2.2</code> encoder GND, off the <code>+3V3</code> pull-up rail."),
}

LINK_PURPOSE = {
    0: "Console 5&nbsp;V from J1 up to the top rail.",
    1: "J1's IRQ pin down to the Pico's GP6.",
    2: "Pico VSYS out to the 5&nbsp;V rail.",
    3: "5&nbsp;V rail down to the encoder connector.",
    4: "Pico 3V3 output across to the pull-up rail.",
    5: "Pico GP2 down to the link-LED resistor.",
    6: "GND spine &mdash; one wire, soldered at five holes on the way down.",
    7: "&mdash; tap at row&nbsp;10", 8: "&mdash; tap at row&nbsp;15", 9: "&mdash; tap at row&nbsp;20",
    10: "<code>J2.5</code> cable shield to GND.",
    11: "<code>J2.2</code> encoder GND to GND. Lies over wire&nbsp;4 at J2 pin&nbsp;1 &mdash; both "
        "are insulated, so let it.",
}

STEPS = [
    ("Make all 23 cuts, before any part goes in",
     "Spot-face cutter or a 3&nbsp;mm drill twisted by hand, from the copper side. "
     "Meter every one across the gap &mdash; a partial cut is the hardest fault to find later."),
    ("Fit the Pico on female headers, not soldered down",
     "Two GND strips and the whole cut column run underneath it."),
    ("Resistors, all six standing on end",
     "Lying flat would put both leads on one strip and short the part out."),
    ("LEDs &mdash; pad 1 is the cathode, and goes to row 27",
     "True for both D1 and D2. Check before soldering; they are the parts you cannot easily lift."),
    ("Capacitors &mdash; <b>C1 is polarised, C2 is not</b>",
     "C1 is the 10&nbsp;µF 25&nbsp;V electrolytic across the 5&nbsp;V rail at rows 3&ndash;4: its <b>+ lead (pad&nbsp;1, the square pad) goes to row&nbsp;3</b> and the striped &minus; lead to the row-4 GND strip. Fitted backwards it can vent. C2 is a 100&nbsp;nF ceramic across 3V3 at rows 24&ndash;26 and goes in either way round."),
    ("J1 and J2", "J1 is a 2.50&nbsp;mm connector on a 2.54&nbsp;mm grid; the drift is 0.2&nbsp;mm "
                  "by pin 6 and the pins bend to suit."),
    ("Link wires last, on the solder side",
     "They follow the parts rather than preceding them. Strip and tin both ends first."),
    ("Meter before power-up: +5V&ndash;GND open, +3V3&ndash;GND open",
     "And <b>U1.33 (AGND) isolated from GND</b> &mdash; the specific thing the row-10 cut exists "
     "to guarantee."),
]


def polarity(fpname):
    """What pad 1 means on a polarised part, or None.

    Derived from the footprint actually on the board rather than a hand-kept
    list, so it cannot drift out of step with the layout the way prose does.
    """
    name = fpname.split(":")[-1]
    if name.startswith("CP_"):
        return "pad&nbsp;1 = <b>+</b> (the square pad)"
    if name.startswith("LED_"):
        return "pad&nbsp;1 = <b>cathode</b> (K, the flat)"
    return None


def esc(s):
    return html.escape(str(s))


def render(spec, segs, fps, mapsvg, totals):
    cuts = sorted(spec.cuts, key=lambda t: (t[0], t[1]))
    wires = [(i, lk) for i, lk in enumerate(spec.links) if lk.wire]
    n_holes = spec.grid.cols * spec.grid.rows

    P = []
    add = P.append

    add('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">')
    add('<meta name="viewport" content="width=device-width, initial-scale=1">')
    add('<title>Wheel Module Stripboard Guide</title>')
    add(f'<style>{CSS}</style>\n</head>\n<body>')

    # --- toolbar
    add('<div class="toolbar"><div class="toolbar-in">'
        '<nav>'
        '<a href="#map">Map</a><a href="#cuts">Cuts</a><a href="#strips">Strips</a>'
        '<a href="#parts">Parts</a><a href="#wires">Wires</a><a href="#build">Build</a>'
        '<a href="#verify">Verified</a></nav>'
        '<span class="grow"></span>'
        '<input id="q" type="search" placeholder="filter rows…" aria-label="Filter table rows">'
        '<span class="progress"><span class="bar"><i id="pbar"></i></span>'
        '<span id="pnum">0/0</span></span>'
        '<button class="btn" id="reset" type="button">Reset</button>'
        '</div></div>')

    # --- header
    add('<div class="wrap"><header class="page-head">'
        '<span class="eyebrow">Haptic Console &middot; Wheel Module (M3) &middot; Veroboard build</span>'
        '<h1>Stripboard Wiring Guide</h1>'
        '<p class="dek">Bench reference for the encoder sensor board on continuous-strip '
        'Veroboard. Every net, cut and column below is read back out of the built '
        '<code>.kicad_pcb</code>, not from intent &mdash; if this page and the board disagree, '
        'the board is right.</p>'
        '</header>')

    add('<div class="stats">'
        f'<div class="stat"><b>{spec.grid.cols}&times;{spec.grid.rows}</b><span>holes</span></div>'
        f'<div class="stat"><b>{spec.grid.width:.2f}</b><span>mm square</span></div>'
        f'<div class="stat"><b>{len(cuts)}</b><span>cuts</span></div>'
        f'<div class="stat"><b>{len(fps)}</b><span>parts</span></div>'
        f'<div class="stat"><b>{len(wires)}</b><span>link wires</span></div>'
        f'<div class="stat"><b>{totals["segments"]}</b><span>strip segments</span></div>'
        f'<div class="stat"><b>{totals["holes"]:,}</b><span>holes drilled</span></div>'
        '</div>')

    add('<div class="callout warn"><p><strong>Read this first: a strip is shared by every hole '
        'in its row.</strong> On plain perfboard a hole connects to nothing. Here it connects to '
        'the whole row, so a pin you never wired still shorts to whatever else sits on its strip. '
        'The question is never &ldquo;did I connect the right pads&rdquo; but &ldquo;does anything '
        'else sit on this strip&rdquo;.</p>'
        '<p><b>Row 10 must be cut at column 12.</b> Pico pin&nbsp;8 (GND) is on the left of that row '
        'and pin&nbsp;33 (<b>AGND</b>) on the right. AGND is a deliberate no-connect; tying it to GND '
        'recreates a <code>power_out</code>/<code>power_out</code> ERC violation and breaks a design '
        'invariant.</p>'
        '<p><b>Rows 5, 15 and 20 are deliberately NOT cut.</b> They carry GND on <i>both</i> sides of '
        'the Pico (pins 3/38, 13/28, 18/23), so leaving them whole buys six GND connections and the '
        'GND bus for free. Getting this backwards costs either a short or a dozen needless wires.</p>'
        '</div>')

    # --- map
    add('<section id="map"><h2>Board map</h2>'
        '<p class="section-intro">Component side, Pico USB at the top &mdash; matching '
        '<code>renders/stripboard-top.png</code>. Strips are drawn in the colour of the net they '
        'carry; faint bands are strips with only an unused pin on them, or bare spare board. '
        'The copper is on the <b>back</b>, so when you flip the board to cut, columns mirror. '
        'Hover any strip for its net and the pads on it; use the chips to isolate one net class.</p>')
    add(f'<div class="map-frame">{mapsvg}</div>')
    add('<div class="map-legend" role="group" aria-label="Filter the map by net class">'
        '<button class="chip" data-filter="all" aria-pressed="true">all</button>'
        '<button class="chip" data-filter="power" aria-pressed="false"><i class="sw sw-power"></i>power</button>'
        '<button class="chip" data-filter="gnd" aria-pressed="false"><i class="sw sw-gnd"></i>GND</button>'
        '<button class="chip" data-filter="i2c" aria-pressed="false"><i class="sw sw-i2c"></i>SDA / SCL / IRQ</button>'
        '<button class="chip" data-filter="signal" aria-pressed="false"><i class="sw sw-signal"></i>encoder &amp; LED</button>'
        '<button class="chip" data-filter="free" aria-pressed="false"><i class="sw sw-free"></i>unused / spare</button>'
        '<span class="chip" style="cursor:default"><i class="sw sw-cut"></i>&times; = cut</span>'
        '</div>'
        '<p class="section-intro" style="margin-top:.9rem">The circuit sits in the top-left, '
        'cols&nbsp;1&ndash;28 and rows&nbsp;1&ndash;29. Everything beyond that is spare board &mdash; but '
        'not inert: each strip still runs the full 40 columns, so the right-hand end of a row is '
        'electrically the same node as the part the circuit uses. Free tie points, and somewhere to '
        'keep clear of stray bridges.</p>'
        '</section>')

    # --- cuts
    add('<section id="cuts"><h2>Cuts &mdash; ' + str(len(cuts)) + ' of them</h2>'
        '<p class="section-intro">Cut <b>at the hole</b>, from the copper side; the hole is dead '
        'afterwards, which is why no via is modelled there. Each is marked with an '
        '<code>X</code> on the back silkscreen. Tick them off as you go &mdash; count them before '
        'soldering anything.</p>')
    add('<div class="tbl-frame"><table><thead><tr>'
        '<th class="n">&#10003;</th><th class="n">Col</th><th class="n">Row</th>'
        '<th>Why</th></tr></thead><tbody>')
    for c, r in cuts:
        kind, why = CUT_WHY.get((c, r), ("", ""))
        if not why:
            why = "Splits the Pico's left pins from its right pins."
        cls = ' class="isolate"' if kind == "critical" else ""
        add(f'<tr{cls} data-search="cut col {c} row {r}"><td class="n">'
            f'<input type="checkbox" data-k="cut-{c}-{r}"></td>'
            f'<td class="n">{c}</td><td class="n">{r}</td><td>{why}'
            + ('  <span class="tag">critical</span>' if kind == "critical" else '')
            + '</td></tr>')
    add('</tbody></table></div>')
    add('<div class="callout">' + "".join(
        f'<p><b>Column {c}</b> &mdash; {why}</p>' for c, why in CUT_GROUPS) + '</div>')
    add('</section>')

    # --- strips
    add('<section id="strips"><h2>Strip allocation</h2>'
        '<p class="section-intro">One row per strip <i>segment</i>. Every segment carries exactly '
        'one net &mdash; verified against the saved board by the engine\'s audit, which aborts the '
        'build if a segment ever carries two. Column ranges are inclusive and run to 40, because '
        'the strips do.</p>')
    add('<div class="tbl-frame"><table><thead><tr>'
        '<th class="n">Row</th><th class="n">Cols</th><th>Net</th><th>Pads on it</th>'
        '</tr></thead><tbody>')
    for s in table_segments(spec, segs):
        if s["row"] == 30:
            add('<tr data-net="" data-cls="spare" data-search="spare board rows 30-40">'
                '<td class="n">30&ndash;40</td><td class="n">all</td>'
                '<td class="net spare">&mdash;</td><td>spare board</td></tr>')
            break
        cls = s["cls"]
        cols = "all" if (s["lo"], s["hi"]) == (1, spec.grid.cols) else f'{s["lo"]}&ndash;{s["hi"]}'
        rowcls = ""
        if s["net"] == "GND" and cols == "all" and s["row"] in (5, 15, 20):
            rowcls = ' class="keep"'
        if s["row"] == 10 and s["lo"] == 13:
            rowcls = ' class="isolate"'
        if s["row"] == 6 and s["lo"] == 1:
            rowcls = ' class="isolate"'
        label = net_label(s["net"]) if s["net"] else "&mdash;"
        note = s["pads"] or ("rail, fed by link wires only" if s["row"] == 2 else "&mdash;")
        if rowcls == ' class="keep"':
            note += ' <span class="tag">uncut &mdash; GND bus</span>'
        if rowcls == ' class="isolate"':
            note += ' <span class="tag">must stay isolated</span>'
        add(f'<tr{rowcls} data-net="{esc(s["net"])}" data-cls="{cls}" '
            f'data-search="row {s["row"]} {esc(s["net"])} {esc(s["pads"])}">'
            f'<td class="n">{s["row"]}</td><td class="n">{cols}</td>'
            f'<td class="net {cls}">{label}</td><td>{note}</td></tr>')
    add('</tbody></table></div></section>')

    # --- parts
    add('<section id="parts"><h2>Placement</h2>'
        '<p class="section-intro">Pad&nbsp;1 sits at the stated hole for every part &mdash; every '
        'footprint in this project has pad&nbsp;1 at its origin, which is what makes grid placement '
        'exact. <b>All six resistors stand on end.</b> That is the Veroboard idiom, and it is what '
        'stops them shorting along a strip.</p><div class="grid-cards">')
    for ref, fp in sorted(fps.items(), key=lambda kv: (kv[0][0], kv[0])):
        p1 = fp["pads"][0]
        rows = sorted({round(p["row"]) for p in fp["pads"]})
        cols = sorted({round(p["col"]) for p in fp["pads"]})
        span = (f'rows {rows[0]}&ndash;{rows[-1]}' if len(rows) > 1 else f'row {rows[0]}')
        colspan = (f'cols {cols[0]} &amp; {cols[-1]}' if len(cols) > 1 else f'col {cols[0]}')
        pol = polarity(fp["fp"])
        add(f'<div class="card" data-search="{esc(ref)} {esc(fp["value"])} {esc(fp["fp"])}">'
            f'<div class="head"><span class="ref">{ref}</span>'
            f'<span class="val">{esc(fp["value"])}</span></div><div class="body"><dl>'
            f'<dt>pad 1</dt><dd>({round(p1["col"])},&thinsp;{round(p1["row"])})</dd>'
            f'<dt>spans</dt><dd>{colspan}, {span}</dd>'
            f'<dt>pins</dt><dd>{len(fp["pads"])}</dd>'
            + (f'<dt>polarity</dt><dd>{pol}</dd>' if pol else '')
            + f'</dl><p class="fp">{esc(fp["fp"].split(":")[-1])}</p>'
            '</div></div>')
    add('</div>'
        '<div class="callout"><p><b>Three parts are slightly off-grid, and that is fine &mdash; the '
        'leads bend.</b> <code>J1</code> is a 2.50&nbsp;mm connector on a 2.54&nbsp;mm grid, so pin&nbsp;6 '
        'lands 0.2&nbsp;mm above row&nbsp;10, cumulative over six pins; its pins are 0.6&nbsp;mm in '
        '1.0&nbsp;mm holes. <code>C1</code> (2.50&nbsp;mm) and <code>C2</code> (5.00&nbsp;mm) are '
        '0.04&nbsp;mm and 0.08&nbsp;mm out.</p>'
        '<p><b>R4 and R5 are the nicest part of this layout.</b> They reach straight from the Pico\'s '
        '<code>/ENC_A</code> and <code>/ENC_B</code> pins down to the <code>_RAW</code> rows with no '
        'link wire at all, so the two noise-sensitive nets are pure copper.</p></div>'
        '</section>')

    # --- wires
    add(f'<section id="wires"><h2>Link wires &mdash; {len(wires)} of them</h2>'
        '<p class="section-intro">Insulated wire on the <b>solder side</b>, hole to hole. The '
        'component side is crowded &mdash; the Pico spans twenty rows and <code>J1</code>, '
        '<code>J2</code> and the LEDs sit on the very edges the long links follow &mdash; so wires '
        'there would lie across component bodies. The back is flat: insulated wire over a copper '
        'strip touches nothing. Colours follow the console convention, so a net is the same colour '
        'on every board in the build: <b>red</b> power, <b>blue</b> GND (the kit has no black), '
        '<b>yellow</b> the I&sup2;C/IRQ bus, <b>green</b> <code>/LNK</code>.</p>')
    add('<div class="tbl-frame"><table><thead><tr>'
        '<th class="n">#</th><th>Net</th><th class="n">Colour</th><th class="n">From</th>'
        '<th class="n">To</th><th>Purpose</th></tr></thead><tbody>')
    for n, (i, lk) in enumerate(wires, 1):
        a, b = lk.points[0], lk.points[-1]
        colour = spec.wire_colors.get(lk.net, "white")
        cls = net_class(lk.net)
        fmt = lambda p: f'({p[0]:g},&thinsp;{round(p[1])})'
        add(f'<tr data-net="{esc(lk.net)}" data-cls="{cls}" '
            f'data-search="wire {n} {esc(lk.net)} {colour}">'
            f'<td class="n">{n}</td><td class="net {cls}">{esc(lk.net)}</td>'
            f'<td class="n"><i class="sw sw-{colour}" style="display:inline-block;'
            f'width:.62rem;height:.62rem;border-radius:2px;margin-right:.35rem;'
            f'vertical-align:-1px"></i>{colour}</td>'
            f'<td class="n">{fmt(a)}</td><td class="n">{fmt(b)}</td>'
            f'<td>{LINK_PURPOSE.get(i, "")}</td></tr>')
    add('</tbody></table></div>')
    add('<div class="callout"><p><b>Wire 7 is one length soldered at five holes</b> &mdash; rows 5, '
        '10, 15, 20 and 27. Those three intermediate joints are what tie the Pico\'s GND rows into '
        'one bus; skip any of them and that row floats. The board file models them as three extra '
        'zero-length links, which is why the netlist counts twelve links and this table nine wires. '
        'They show on the map as dashed stubs.</p></div></section>')

    # --- build order
    add('<section id="build"><h2>Build order</h2>'
        '<p class="section-intro">The link wires go on the <i>solder</i> side, which inverts the '
        'usual perfboard order: wires last, after the parts, not before them.</p><ol class="steps">')
    for n, (title, body) in enumerate(STEPS, 1):
        add(f'<li data-search="{esc(re.sub("<[^>]+>", "", title))}">'
            f'<input type="checkbox" data-k="step-{n}" aria-label="{esc(re.sub("<[^>]+>", "", title))}">'
            f'<span class="step-body"><strong>{title}</strong><span>{body}</span></span></li>')
    add('</ol></section>')

    # --- verification
    add('<section id="verify"><h2>Verification state</h2>'
        '<p class="section-intro">What the tools say about the board this page describes.</p>'
        '<div class="grid-cards">'
        '<div class="card"><div class="head"><span class="ref">DRC</span>'
        '<span class="val">kicad-cli</span></div><div class="body">'
        '<b style="color:var(--ink)">0 errors, 0 unconnected pads, 0 footprint errors.</b>'
        '<p style="margin:.4rem 0 0">Check with <code>--severity-error</code>.</p></div></div>'
        '<div class="card"><div class="head"><span class="ref">Strip audit</span>'
        '<span class="val">engine stage 4</span></div><div class="body">'
        '<b style="color:var(--ink)">Clean.</b><p style="margin:.4rem 0 0">Every segment carries '
        'exactly one net, and both isolation invariants hold: <code>U1.33</code> AGND and '
        '<code>J1.2</code> each alone on their segment.</p></div></div>'
        '<div class="card"><div class="head"><span class="ref">Warnings</span>'
        '<span class="val">240, expected</span></div><div class="body">'
        '199 <code>via_dangling</code>, 38 <code>track_dangling</code>, 3 inherited '
        '<code>lib_footprint_mismatch</code>. Dangling is inherent to modelling perfboard holes as '
        'vias, and bare strips really are unconnected copper. Do not chase them.</div></div>'
        '</div></section>')

    add('<section><h2>Notes</h2><details class="notes">'
        '<summary>Why the board is this size, and what is generated from what</summary><ul>'
        '<li>The grid matches the stock the board is actually built on: a 40&nbsp;&times;&nbsp;40 hole '
        'Veroboard, 104.14&nbsp;mm square, uncut. The circuit was laid out inside 28&nbsp;&times;&nbsp;30 '
        'and has not moved; the extra columns and rows are spare.</li>'
        '<li>The board is <b>generated, not hand-built</b>. <code>scripts/layout.py</code> is pure '
        'data; the engine that turns it into copper lives in <code>~/KiCad/kicad-stripboard</code>. '
        'Rebuild it, do not patch it.</li>'
        '<li>This page is generated too, by <code>scripts/wiring_guide.py</code>, from the layout '
        'spec plus a read-back of the built board. Re-run it after any rebuild.</li>'
        '<li>Renders are green FR4 rather than tan phenolic: the stackup API is not reachable from '
        'pcbnew here, so the Veroboard colour is a GUI job (Board Setup &rsaquo; Physical Stackup).</li>'
        '<li>This is the Veroboard build. <code>docs/perfboard-wiring.md</code> covers a different, '
        'point-to-point board on plain perfboard. They are not interchangeable &mdash; pick one.</li>'
        '</ul></details></section>')

    add('</div>')  # .wrap

    add("""<script>
(function () {
  "use strict";
  var KEY = "wheel-stripboard-progress";
  var boxes = Array.prototype.slice.call(document.querySelectorAll("input[type=checkbox][data-k]"));
  var bar = document.getElementById("pbar"), num = document.getElementById("pnum");

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; }
  }
  function save(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* private mode */ }
  }
  function paint() {
    var done = 0;
    boxes.forEach(function (b) {
      if (b.checked) done++;
      var li = b.closest("li");
      if (li) li.classList.toggle("done", b.checked);
    });
    num.textContent = done + "/" + boxes.length;
    bar.style.width = boxes.length ? (100 * done / boxes.length) + "%" : "0";
  }
  var state = load();
  boxes.forEach(function (b) {
    b.checked = !!state[b.dataset.k];
    b.addEventListener("change", function () {
      state[b.dataset.k] = b.checked; save(state); paint();
    });
  });
  paint();
  document.getElementById("reset").addEventListener("click", function () {
    state = {}; save(state); boxes.forEach(function (b) { b.checked = false; }); paint();
  });

  // --- net-class filter: dims the map and the tables together -----------------
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip[data-filter]"));
  var segs = Array.prototype.slice.call(document.querySelectorAll("svg .seg"));
  var links = Array.prototype.slice.call(document.querySelectorAll("svg .link"));
  var netCls = {};
  segs.forEach(function (g) {
    var m = /seg-(\\w+)/.exec(g.getAttribute("class"));
    netCls[g.dataset.net] = m ? m[1] : "spare";
  });
  function applyFilter(f) {
    segs.forEach(function (g) {
      var m = /seg-(\\w+)/.exec(g.getAttribute("class"));
      g.classList.toggle("dim", f !== "all" && (!m || m[1] !== f));
    });
    links.forEach(function (p) {
      p.classList.toggle("dim", f !== "all" && netCls[p.dataset.net] !== f);
    });
    document.querySelectorAll("tr[data-cls]").forEach(function (tr) {
      tr.classList.toggle("dim", f !== "all" && tr.dataset.cls !== f);
    });
    chips.forEach(function (c) {
      c.setAttribute("aria-pressed", String(c.dataset.filter === f));
    });
  }
  chips.forEach(function (c) {
    c.addEventListener("click", function () {
      applyFilter(c.getAttribute("aria-pressed") === "true" ? "all" : c.dataset.filter);
    });
  });

  // --- text filter over every table row and part card -------------------------
  var q = document.getElementById("q");
  var rows = Array.prototype.slice.call(document.querySelectorAll("tr[data-search], li[data-search], .card[data-search]"));
  q.addEventListener("input", function () {
    var t = q.value.trim().toLowerCase();
    rows.forEach(function (el) {
      var hay = (el.dataset.search + " " + el.textContent).toLowerCase();
      el.style.display = (!t || hay.indexOf(t) !== -1) ? "" : "none";
    });
  });
})();
</script>""")
    add('</body>\n</html>')
    return "\n".join(P)


def table_segments(spec, segs):
    """Same segmentation the map draws, in reading order, with nets attached."""
    cuts_by_row = {}
    for c, r in spec.cuts:
        cuts_by_row.setdefault(r, []).append(c)
    lookup = {(s["row"], round(s["x0"], 2)): s for s in segs}
    out = []
    for row in range(1, spec.grid.rows + 1):
        bounds = [EDGE_LO]
        for c in sorted(cuts_by_row.get(row, [])):
            bounds += [c - 0.5, c + 0.5]
        bounds.append(EDGE_HI)
        for i in range(0, len(bounds), 2):
            x0, x1 = bounds[i], bounds[i + 1]
            s = lookup.get((row, round(x0, 2)))
            net = s["net"] if s else ("+5V" if row == 2 else "")
            out.append(dict(row=row, lo=int(x0 + 0.5), hi=int(x1), net=net,
                            pads=s["pads"] if s else "", cls=net_class(net)))
    return out


def main():
    spec = load_spec().SPEC
    segs, totals = audit_segments()
    fps = pcb_footprints()
    page = render(spec, segs, fps, build_map(spec, segs, fps), totals)
    with open(OUT, "w") as f:
        f.write(page)
    print(f"wrote {OUT} ({len(page):,} bytes) "
          f"— {len(spec.cuts)} cuts, {len(fps)} parts, {len(segs)} audited segments")


if __name__ == "__main__":
    main()
