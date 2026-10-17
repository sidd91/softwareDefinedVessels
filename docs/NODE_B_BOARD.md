# Node B board: bring-up notes

Status: Sat 11:15 PDT. Brought up headless over ADB by Claude on behalf of Logan Walker (GhostWalka), at
Logan's request (WORKLOG DEC-41). Everything below was measured on the board, not assumed. Hardware
choices stay with the team (DEF-01).

## What the board is

| Item | Measured |
|---|---|
| Board | Arduino VENTUNO Q, USB ID 2341:007a, hostname `training05` (named by the organizers) |
| Processor | 8 cores: 4 Cortex-A78C up to 2.36 GHz and 4 Cortex-A55 up to 1.96 GHz (the Dragonwing QCS8275 of DEC-30) |
| Memory and storage | 14 GiB RAM; 55 GB eMMC with 38 GB free |
| Operating system | Ubuntu 24.04.4 LTS, kernel 6.8.0-1084-qcom, aarch64 (not Debian, as first noted) |
| Python | 3.12.3, the same minor version as the project; PyYAML and jsonschema present; pip, venv, NumPy, OpenCV, ONNX Runtime and FastAPI absent |
| Tools present | git, Docker, `arduino-app-cli`, OpenSSH server (active and enabled), NetworkManager |
| Links | USB-C to the laptop (ADB plus a serial port); Wi-Fi on the venue network; an Ethernet port with no cable |
| Video devices | two unnamed devices (video32, video33); no camera attached |
| Clock | UTC, NTP-synchronised, matches the laptop to the second |
| Idle temperature | 25-26 °C |

## Power

The board needs 5 V at 3 A over USB-C. At first it showed only a flashing red LED and never appeared on
USB; the laptop was on battery. It came up at 11:11 PDT after the power steps. For the demo: keep the
laptop on its charger, or put a powered USB-C hub between laptop and board.

## Link timing

Sat 11:14 PDT: 100 TCP heartbeats of 6 bytes, 100 ms apart, to a temporary echo server on the board
(our own 15 lines, run from /tmp and removed afterwards).

| Path | Median | 95th percentile | Max | Beats over 100 ms |
|---|---|---|---|---|
| USB-C, ADB port forward | 5.5 ms | 6.5 ms | 10.3 ms | 0 |
| Venue Wi-Fi | 6.5 ms | 95.9 ms | 116.1 ms | 3 |

An earlier ping over Wi-Fi gave 90-154 ms. A failover timeout of one or two missed 100 ms beats would
flap on Wi-Fi but holds on USB. That fits the plan's reading of IACS UR E22 (Wi-Fi as backup only).
Timeout values per path are the team's call (CON-16).

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

## Not done yet (installs need Logan's OK)

1. A Python environment on the board: Ubuntu's `python3-venv` and `python3-pip` (needs sudo), or uv's
   per-user installer.
2. ONNX Runtime for aarch64 and opencv-python-headless (approved in DEC-39 for this step), after step 1.
3. The repo on the board: `adb push`, or a git clone over Wi-Fi.
4. The wired path and power arrangement (DEF-01).
