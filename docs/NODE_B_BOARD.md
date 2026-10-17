# Board instrument: the VENTUNO Q

Status: Sat 12:40 PDT. Board facts measured Sat 11:15 PDT by Claude on behalf of Logan Walker (GhostWalka),
over ADB at Logan's request (WORKLOG DEC-41). Role rewritten to the design freeze (DEC-44, delta 10). Who
builds the instrument is not decided.

## Role

Before the freeze this board was node B, a hot-standby governor and camera host. The freeze cut failover,
cameras and NPU inference, and made the board an instrument.

- **What it does.** It runs the same container as the laptop, headless. It replays the Scenario A and
  Scenario B timelines and reports three numbers: watts, latency per decision class (D1 to D5 and safety
  commands), and CPU share against A.7.
- **Where the numbers go.** The Physical Account's compute and response-time rows, as measured values. The
  board is an 8-core edge CPU, not one of A.7's four 32-core nodes, so each row says so and states the
  scale-up as an assumption.
- **What it does not do.** The laptop provides every demo input: the genset trip, the jury's card and its
  one-number edit, the priority swap, the crew level. A board button or knob may only mirror a laptop input.
  Nothing in the demo depends on the board: unplugged, the demo runs the same.

## Measurements to take

| Number | How (proposal for the owner) | Physical Account row |
|---|---|---|
| Latency per decision class | the timing log of a replayed run, median and worst case per class against A.8 (30 s, 2 s, 5 s, 60 s, 200 ms) | response time |
| CPU share | process CPU time over the replay, as a share of the board's 8 cores, then scaled to A.7 (4 nodes x 32 cores, 20 % reserved for ship systems) | compute |
| Watts | not settled: an inline USB-C meter, or the board's own power readings if it exposes them | compute |

The same timing log on the laptop gives the figures the screen shows. The board's figures appear only in the
Physical Account.

## What the board is

| Item | Measured |
|---|---|
| Board | Arduino VENTUNO Q, USB ID 2341:007a, hostname `training05` (named by the organizers) |
| Processor | 8 cores: 4 Cortex-A78C up to 2.36 GHz and 4 Cortex-A55 up to 1.96 GHz (the Dragonwing QCS8275 of DEC-30) |
| Memory and storage | 14 GiB RAM; 55 GB eMMC with 38 GB free |
| Operating system | Ubuntu 24.04.4 LTS, kernel 6.8.0-1084-qcom, aarch64 |
| Python | 3.12.3, the same minor version as the project; PyYAML and jsonschema present; pip, venv and FastAPI absent |
| Tools present | git, Docker, `arduino-app-cli`, OpenSSH server (active and enabled), NetworkManager |
| Links | USB-C to the laptop (ADB plus a serial port); Wi-Fi on the venue network; an Ethernet port with no cable |
| Clock | UTC, NTP-synchronised, matches the laptop to the second |
| Idle temperature | 25-26 °C |

## Power

The board needs 5 V at 3 A over USB-C. At first it showed only a flashing red LED and never appeared on
USB; the laptop was on battery. It came up at 11:11 PDT after the power steps. Keep the laptop on its
charger, or put a powered USB-C hub between laptop and board. The power arrangement stays with the team
(DEF-01).

## Link timing (measured, no longer on the demo path)

Sat 11:14 PDT: 100 TCP heartbeats of 6 bytes, 100 ms apart, to a temporary echo server on the board (our
own 15 lines, run from /tmp and removed afterwards).

| Path | Median | 95th percentile | Max | Beats over 100 ms |
|---|---|---|---|---|
| USB-C, ADB port forward | 5.5 ms | 6.5 ms | 10.3 ms | 0 |
| Venue Wi-Fi | 6.5 ms | 95.9 ms | 116.1 ms | 3 |

These numbers were taken for failover, which the freeze cut. They still show that USB is the steadier path
for copying replays and results.

## How to reach it

```bash
adb devices -l
adb shell
adb forward tcp:8765 tcp:8765
adb reverse tcp:8765 tcp:8765
```

`forward` maps a laptop port to the board; `reverse` maps a board port to the laptop. `adb shell` logs in
as user `arduino` with no password. `sudo` needs the board's password, typed by the person at the keyboard.

## Security (CON-15)

The SSH server is reachable from the shared venue Wi-Fi, and the board still has the default login printed
on the workshop slide, so anyone at the event can log in and use sudo. An `~/.ssh/authorized_keys` file was
already there when we got the board; its contents were not read. Fix, with Logan typing the passwords:

```bash
adb shell -t passwd
```

With failover cut, the instrument needs only USB, so turning Wi-Fi or SSH off on the board would also close
the exposure. That is Logan's call.

## Not done yet

Installs need Logan's OK.

1. The container on the board: how the image is built for aarch64 and moved to the board, or a uv
   environment as a fallback.
2. The repo or the image on the board: `adb push`, or a git clone over Wi-Fi.
3. A measurement script that replays the timelines and writes the three numbers.
4. The power arrangement (DEF-01).

The camera installs once planned for this board (opencv-python-headless and ONNX Runtime) are withdrawn by
DEC-44.
