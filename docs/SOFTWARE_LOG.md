# Software and AI usage log

Every tool, package, model and service used on this project, dev-time or shipped. Kept current as
things are added. "Ships" means it is in the deliverable repo or runs during the live demo.
Policy: open-source third-party code only (OSI licence, no AGPL), or our own; every AI model declared.
The design freeze (WORKLOG DEC-44) cut cameras and computer vision, the 3D view, the crew rule compiler,
the LLM paraphraser, person detection, NPU inference and two-node failover. What those would have used
is listed under [Excluded by the design freeze](#excluded-by-the-design-freeze-dec-44).

## Needs action from Logan
| Item | Why | Status |
|---|---|---|
| `gh auth login` as GhostWalka | team repo is private | done Fri 20:40 PDT |
| Record where the authorized AI list was published (asked in [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md)) | the list's source is not recorded (next section); the message also asked about the submission, the simulator, the memo and Scenario B minute 12 | message sent by Logan Sat 12:31 PDT (WORKLOG DEC-49); answers in DEC-49 to DEC-51; the list's source is still open |

## Authorized AI list (brief, Data Use Authorization 2)
The brief allows an AI service only if it is "included in the authorized list published before Day 0", and
the rule covers coding assistants. Claude is approved on Logan's word (WORKLOG DEC-05), and every AI model
used so far is a Claude model (first two rows below). Where the list was published, and when, is not yet
recorded. The question was sent in [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md) (Sat 12:31 PDT, DEC-49); the
answers so far do not name the list's source. The source and date go here when they come.

## Installed or already present on the laptop
| Software | Version | Licence | Origin | Purpose | Ships | Status |
|---|---|---|---|---|---|---|
| Claude Fable 5.1 (Claude Code desktop) | claude-fable-5-1 | service | Anthropic, US | coding assistant, docs drafting, research | no (declared) | in use, approved by Logan for the event (DEC-05) |
| Claude Opus 5.5 (Claude Code desktop) | claude-opus-5-5 | service | Anthropic, US | coding assistant, brainstorming, docs drafting; switched in by Logan 2026-10-16 ~22:40 CDT | no (declared) | in use, approved (DEC-05) |
| uv | present | MIT / Apache-2.0 | Astral, US | Python version + dependency manager | no (dev) | present |
| Python | 3.12.15 via uv for the project; 3.14.4 system unused | PSF | PSF | runtime | yes | in use since Fri 21:40 PDT, pinned in `.python-version` |
| git | present | GPL-2.0 | — | version control | no | present |
| GitHub CLI (gh) | present | MIT | GitHub | repo access | no | present, signed in as GhostWalka |
| Docker | present | Apache-2.0 | Docker Inc. | may build the container that the board instrument also runs (DEC-44); who builds it is not decided | not decided | unused so far |
| PyYAML | 6.0.3 | MIT | PyYAML team | read assumptions, cards, priority files | yes | installed Fri 21:40 PDT into the project `.venv` |
| jsonschema (+ attrs, referencing, rpds-py, jsonschema-specifications, typing-extensions) | 4.26.0 | MIT (deps MIT; typing-extensions PSF-2.0) | Julian Berman et al. | validate guest manifests | yes | installed Fri 21:40 PDT |
| pytest (+ iniconfig, packaging, pluggy, pygments) | 9.1.1 | MIT (deps MIT / Apache-2.0 / BSD-2) | pytest devs | tests | no (dev) | installed Fri 21:40 PDT |
| hatchling | build backend, fetched by uv into an isolated build env | MIT | PyPA | builds the `sdv-governor` package | no (build) | used by `uv sync` |
| OpenCV (opencv-python-headless) and NumPy | 5.0.0.93 and 2.5.3 | Apache-2.0; BSD-3 | OpenCV.org; NumPy devs | CPU timing benches by a camera research agent, Fri about 23:30 PDT, on synthetic frames; that camera work is cut (DEC-44) | no | nothing installed: both were already in the laptop's uv cache from Oct 9 and were used through PYTHONPATH; the project environment is unchanged |
| LibreOffice | 26.2.6.3 (system package) | MPL-2.0 | The Document Foundation | page-count renders of the Scenario C memo and README by a requirements agent, Sat about 00:20 PDT; now the fallback route in `tools/build_pdfs.py` | no | nothing installed: already on the system; the early renders went to /tmp |
| poppler-utils (`pdfinfo`) | 26.01.0-2ubuntu0.2 (system package) | GPL-2.0 or GPL-3.0 | Poppler developers, built by Ubuntu | page counts in `tools/build_pdfs.py` | no (dev) | nothing installed: already on the system |
| adb (Android Debug Bridge) | 1:34.0.5-12build1, Ubuntu universe | Apache-2.0 | AOSP source, built by Ubuntu | headless shell and port forwarding to the board over USB-C | no (dev); the USB link may carry the board instrument's readings (DEF-01) | installed Sat 11:07 PDT at Logan's request; Logan typed sudo |
| pandoc | 3.7.0.2+ds-1, Ubuntu universe | GPL-2.0-or-later | John MacFarlane et al., Ubuntu | Markdown to HTML for the deliverable PDFs (`tools/build_pdfs.py`) | no (dev) | installed Sat 11:47 PDT at Logan's request; Logan typed sudo |
| Chromium (snap) | 155.0.8059.79 | BSD-3-Clause and others (Chromium licences) | Canonical snap of the Chromium project | headless print of the deliverable PDFs (`tools/build_pdfs.py`) | no (dev) | installed Sat 11:47 PDT at Logan's request |
| android-sdk-platform-tools-common | 28.0.2+12, Ubuntu universe | Apache-2.0 | AOSP, Ubuntu | udev rules giving USB access without root | no | installed Sat 11:07 PDT with adb |
| FastAPI (+ Starlette 1.8.0 BSD-3-Clause, pydantic 2.14.1 MIT, pydantic-core 2.50.1 MIT, annotated-doc 0.0.5 MIT, annotated-types 0.8.0 MIT, typing-inspection 0.4.4 MIT, anyio 4.15.1 MIT, idna 3.20 BSD-3-Clause, opentelemetry-api 1.45.1 Apache-2.0) | 0.143.3 | MIT | Sebastián Ramírez (deps: Encode, Pydantic Services, Alex Grönholm, Kim Davies, OpenTelemetry/CNCF) | HTTP and websocket server for the ArgOS screen (`src/sdv/ui/`) | yes | installed Sat 14:51 PDT (approved DEC-39) |
| uvicorn (+ click 8.5.0 BSD-3-Clause, h11 0.16.0 MIT) | 0.54.0 | BSD-3-Clause | Encode (deps: Pallets, python-hyper) | ASGI server behind `uv run python -m sdv.ui.server` | yes | installed Sat 14:51 PDT (approved DEC-39) |
| websockets | 17.2 | BSD-3-Clause | Aymeric Augustin | websocket protocol for uvicorn (`/ws` pushes snapshot and records per tick); also the client in the UI tests | yes | installed Sat 14:51 PDT (approved DEC-39) |
| Superpowers plugin for Claude Code (obra/superpowers) | 6.4.2 | MIT | Jesse Vincent, Anthropic plugin directory (partner tier) | development workflow skills: TDD, plans, debugging, verification, subagent-driven development | no (dev) | install card shown to Logan Fri 21:36 PDT |

## Present on the board (VENTUNO Q `training05`); nothing installed by us
Survey Sat 11:12 PDT; details in [NODE_B_BOARD.md](NODE_B_BOARD.md), which calls the board node B.
The board is an instrument (DEC-44). It runs the same container as the laptop and reports watts, latency
per decision class and CPU share against A.7 for the Physical Account. Nothing in the demo depends on it.
| Software | Version | Licence | Purpose | Ships | Status |
|---|---|---|---|---|---|
| Ubuntu | 24.04.4 LTS, kernel 6.8.0-1084-qcom | mixed open source | board OS, host for the instrument container | instrument only | preinstalled by the organizers |
| Python | 3.12.3 | PSF | board runtime | no | preinstalled; the container brings its own Python |
| PyYAML, jsonschema | system packages | MIT | cards and assumptions | no | preinstalled; the container brings its own |
| git, Docker, OpenSSH, NetworkManager | system packages | GPL-2.0, Apache-2.0, BSD, GPL-2.0 | repo copy, the instrument container, network | no | preinstalled; Docker not used yet |
| arduino-app-cli | preinstalled | not checked | Arduino App Lab back end | no | preinstalled; unused by us |
| Echo server for link timing | our own, 15 lines | ours | measured USB and Wi-Fi heartbeat round trips for the failover plan, now cut (DEC-44) | no | ran Sat 11:14 PDT from /tmp, then removed |

## Planned (approved by Logan, DEC-39; added to the table above when actually installed)
FastAPI, uvicorn and websockets were installed Sat 14:51 PDT and moved to the installed table, with versions and licences.

Their transitive dependencies (pydantic and Starlette under FastAPI, click and h11 under uvicorn) are logged
with versions and licences in the installed table, as for jsonschema. DEC-39 also approved
opencv-python-headless and onnxruntime for the camera and board steps. DEC-44 cut both uses, so neither is
planned; both are listed under [Excluded by the design freeze](#excluded-by-the-design-freeze-dec-44).

## Considered, not approved
Named in planning documents but covered by no approval. Nothing here is installed or downloaded; each
needs Logan's approval before it is.
| Software or model | Licence | Origin | Considered for | Note |
|---|---|---|---|---|
| pydantic | MIT | Pydantic Services | manifest and rule models | arrives as a FastAPI dependency (DEC-39); not approved as a direct dependency of the core |
| NumPy | BSD-3 | NumPy devs | ledger math | not approved for the core; no planned package brings it in now that opencv and onnxruntime are excluded |
| httpx | BSD-3 | Encode | one-time Open-Meteo Marine fetch, cached | dev only |
| OR-Tools | Apache-2.0 | Google | optional solver for D2 placement | not planned: D1 and D2 run by enumeration (design freeze) |
| ReportLab or WeasyPrint | BSD-3 | ReportLab Inc.; Kozea | memo and Physical Account to PDF | the PDF route is `tools/build_pdfs.py` instead |

## Data sources (planned; none downloaded yet)
Full tiered list with sizes in `research/SENSOR_CATALOG.md`. Each is declared here when pulled.
| Source | Licence | Status |
|---|---|---|
| Open-Meteo Marine and Archive | CC BY 4.0, free tier non-commercial | planned; the brief itself names Open-Meteo Marine as a tier-2 public source (Stack, data and tools), so no organizer check is needed (CON-05); attribution line in the README when cached |
| NOAA OISST via ERDDAP | public domain | planned |
| Argo via Ifremer ERDDAP | free and open | planned |
| UCI naval propulsion CBM | CC BY 4.0 | planned |
| Zenodo tanker auxiliary load profiles | CC BY 4.0 | planned |
| Zenodo marine engine fault set | CC BY 4.0 | planned |
| PX4 Flight Review logs | CC BY | planned |
| CMU M100 drone energy | CC BY 4.0 | planned |

## Excluded by the design freeze (DEC-44)
DEC-44 (Sat 12:04 PDT) cut cameras and computer vision, the 3D view, the crew rule compiler and its
controlled grammar, the LLM paraphraser, person detection, NPU inference and two-node failover. Nothing
below was installed or downloaded; the only use was the timing bench in the installed table. Rows moved
here Sat 12:32 PDT. The research behind them stays in `research/`, marked superseded.
| Item | Licence | Origin | Was planned for | Earlier decision | Status |
|---|---|---|---|---|---|
| opencv-python-headless | Apache-2.0 (OpenCV); MIT packaging; the wheel bundles FFmpeg under LGPL-2.1 (its LICENSE-3RD-PARTY.txt) | OpenCV.org | camera capture and frame handling for the equipment watch (leak, smoke, deck gear) | DEC-39 | not installed; no longer planned for CV |
| onnxruntime | MIT | Microsoft | detector models on the board's CPU | DEC-31, DEC-39 | not installed; no longer planned |
| three.js (one vendored file) | MIT | three.js authors | 3D ship view, a toggle beside the 2D screen | DEC-04, DEC-13 | not downloaded |
| Crew rule compiler and controlled grammar | ours | our own code | crew rules entered as text through an approved grammar, with no LLM-written code | DEC-02 | not built |
| Lark | MIT | Erez Shinan | parser for the crew-rule grammar | none (DEC-02 approved the grammar, not the library) | not installed |
| Phi-4-mini or Mistral-7B-Instruct | MIT / Apache-2.0 | Microsoft / Mistral AI | offline paraphrase of free text into rule-grammar text | none | not downloaded; no LLM runs in the build |
| torch + torchvision, SSDlite320-MobileNetV3 with COCO weights | BSD-3; weights terms inherit COCO's | Meta | person detector | DEC-13 (proposed), DEC-23 | not installed |
| MediaPipe EfficientDet-Lite0 | Apache-2.0 code; weights licence unconfirmed | Google | detector on the board | none | not downloaded |
| opencv-python (full build) | Apache-2.0 | OpenCV.org | webcam capture | none | not installed |
| NPU inference (Qualcomm QAIRT SDK with the ONNX Runtime QNN execution provider) | proprietary SDK; MIT provider | Qualcomm; Microsoft | detectors on the board's NPU | DEC-14, DEC-31 | not used; the QAIRT row under Excluded on purpose still applies |
| Two-node failover (our own heartbeats, epochs, duplicate paths, failover by replay, Wi-Fi backup) | ours | our own code | governor hot standby on the board | DEC-06, DEC-14, DEC-26 | not built; websockets stays for the browser screen only |
| SeaDronesSee subset | CC0 | Univ. of Tübingen | detector evaluation at sea | none | not downloaded |
| MaSTr1325 frames | CC BY 4.0 | ViCoS, Univ. of Ljubljana | camera horizon-tilt check | none | not downloaded |

## Excluded on purpose
| Software | Reason |
|---|---|
| Ultralytics YOLO | AGPL-3.0 would bind the whole served application |
| Llama, Gemma | community licences are not OSI open source |
| Any model from a China-based company or derived from one (Qwen, DeepSeek, Yi, GLM, YOLOX, YOLOv6, YOLOv10, RT-DETR, D-FINE, LW-DETR, DAMO-YOLO, PP-YOLO, PaddleOCR) | brief, Data Use Authorization §2 |
| RF-DETR (Roboflow) | built on LW-DETR from Baidu; excluded as China-derived |
| OpenCV `wechat_qrcode` module | CNN models contributed by Tencent |
| DeepShip dataset | China origin (NWPU); same source audio available from Ocean Networks Canada |
| Node / React | no build step wanted; nothing installed; vanilla JS + vendored libs run offline |
| Any cloud inference or training | Logan's rule: runtime compute local only (DEC-01) |
| Qualcomm AI Hub, Edge Impulse | cloud compile and training; models stay local (DEC-31) |
| Qualcomm QAIRT SDK (proprietary NPU runtime) | not used unless the organizers clear it (DEC-31); NPU inference is also cut (DEC-44) |
| Datasets: CWRU, Paderborn, FuelCast, CRAWDAD, DeepShip, XJTU-SY, HUST, FLIR ADAS, Girona caves | no licence, non-commercial, no redistribution, or China origin |
