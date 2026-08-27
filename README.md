# Haptic Console - Wheel Module (M3) Encoder Sensor Board

KiCad project for the electronics of the Wheel Module (M3) of Haptic Console v1.0,
part of the ITPMA dissertation *Tactile I/O: Exploring physicality in MIDI controllers*.

The mechanical side of this module (200 mm DIN aluminium handwheel, PETG shaft,
6204-2RS bearings, GT2 1:1 belt drive) is documented in the Obsidian vault under
`Notes/Haptic Console - Handwheel Belt Drive Module Plan.md`. This repository covers
only the sensor board that reads the optical encoder and presents it to the console.

## What the board does

The handwheel drives a 600 P/R optical encoder through a 1:1 GT2 belt. A Raspberry Pi
Pico reads the A/B/Z quadrature signals locally, converts them into a clean position
packet, and exposes that packet to the Teensy 4.1 master over I2C. The module behaves
as a self-contained tactile sense organ rather than a peer processor, matching the
connector standard's design philosophy.

## The encoder interface, and why the pull-ups are there

The encoder is a photoelectric incremental type rated **DC 5-24V** with **NPN
open-collector** outputs. This is the important detail. An open-collector output can
only pull its line *low*. It never drives a line high. The high level is therefore set
entirely by whatever rail the line is pulled up to, and is completely independent of
the encoder's own supply voltage.

That gives the safety property this board relies on:

- `R1`, `R2`, `R3` (4.7k) pull `ENC_A_RAW`, `ENC_B_RAW`, `ENC_Z_RAW` up to **+3V3**.
- The Pico therefore sees a 0V to 3.3V swing regardless of whether the encoder is run
  from 5V or 12V.
- `R4`, `R5`, `R6` (220R) sit in series into the Pico GPIO as fault-current limiters,
  protecting the pin if a line is ever accidentally shorted to the encoder supply.

Without the pull-ups the inputs would float and the quadrature decode would be noise.
The pull-ups are not optional here.

Encoder power is taken from the console's **5V rail**, which is inside the encoder's
rated 5-24V window. If the encoder proves sluggish or noisy at 5V, the documented
alternative is a small 5V to 12V boost feeding `J2` pin 1 only. Because the pull-ups
reference 3.3V, that change requires **no** modification to the logic side.

## Console interface

`J1` is the standard **XH2.54 6-pin** inter-module connector (standard v1.1):

| Pin | Signal | Board use |
|---|---|---|
| 1 | GND | Common ground |
| 2 | 3.3V | **Not connected** (see below) |
| 3 | 5V | Powers the Pico via VSYS, and the encoder |
| 4 | SIG1 / SDA | I2C data, Pico GP4 |
| 5 | SIG2 / SCL | I2C clock, Pico GP5 |
| 6 | SIG3 / IRQ | Data-ready, Pico GP6 |

Pin 2 is deliberately left unconnected. The connector standard warns against feeding
both VSYS and 3V3 as competing power paths into a Pico. The board takes 5V into VSYS
and uses the Pico's own regulated 3V3 output as the logic reference for the pull-ups.

I2C bus pull-ups live on the master/hub board, not here, per the same standard.

## Pin map

| Pico pin | Net | Function |
|---|---|---|
| GP2 (pin 4) | LNK | Link/comms status LED |
| GP4 (pin 6) | SDA | I2C target data |
| GP5 (pin 7) | SCL | I2C target clock |
| GP6 (pin 9) | IRQ | Data-ready out to master |
| GP16 (pin 21) | ENC_A | Encoder channel A |
| GP17 (pin 22) | ENC_B | Encoder channel B |
| GP18 (pin 24) | ENC_Z | Encoder index (optional) |
| VSYS (pin 39) | +5V | Module power in |
| 3V3 (pin 36) | +3V3 | Logic reference out |

At 600 P/R with 4x quadrature decoding, one full handwheel turn is 2400 counts.

## Bill of materials

| Ref | Value | Footprint |
|---|---|---|
| U1 | Raspberry Pi Pico | Module:RaspberryPi_Pico_Common_THT |
| J1 | XH2.54 6-pin console connector | Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical |
| J2 | 5-pin encoder header | Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical |
| R1-R3 | 4.7k pull-up to 3.3V | Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal |
| R4-R6 | 220R series protection | Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal |
| R7, R8 | 1k LED current limit | Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal |
| C1 | 10uF bulk on 5V | Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm |
| C2 | 100nF decoupling on 3.3V | Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm |
| D1 | PWR green 3mm | LED_THT:LED_D3.0mm |
| D2 | LNK red 3mm | LED_THT:LED_D3.0mm |

D1 and D2 match the PWR/LNK status cluster in the front panel drawing
(`Notes/Haptic Console - Wheel Module Front Panel.md`).

## Status

- Schematic: complete, **ERC 0 errors / 0 warnings**, netlist verified by inspection.
- PCB layout: **not started**.
- Cosmetic: reference and value text is auto-placed and overlaps net labels in a few
  places. Harmless electrically, but worth a tidy-up pass in the GUI before the
  schematic goes into the dissertation.

## Verification

```bash
export KICAD_SYMBOL_DIR=/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols
export KICAD_FOOTPRINT_DIR=/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints
kicad-cli sch erc --format report project/haptic-console-wheel-module.kicad_sch -o docs/erc-report.txt
kicad-cli sch export netlist --format kicadsexpr project/haptic-console-wheel-module.kicad_sch -o docs/netlist.net
```

Setting both environment variables matters. Without them `kicad-cli` cannot resolve the
stock libraries and reports spurious violations.

## Related

- `../control-unit-kicad` - the Control Unit (M6) board, already fab-ready
- Obsidian: `Notes/Haptic Console - Connector Standard.md`
- Obsidian: `concepts/haptic-console-wheel-module.md`
