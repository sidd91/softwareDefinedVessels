# Software and AI usage log

Every tool, package, model and service used on this project, dev-time or shipped. Kept current as
things are added. "Ships" means it is in the deliverable repo or runs during the live demo.
Policy: open-source third-party code only (OSI licence, no AGPL), or our own; every AI model declared.

## Needs action from Logan
| Item | Why | Status |
|---|---|---|
| `gh auth login` as GhostWalka | team repo is private | done Fri 20:40 PDT |
| Send the organizer message in [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md) | the authorized AI list's source is not recorded (next section); it also asks about the submission format | drafted Sat 11:43 PDT; not sent |

## Authorized AI list (brief, Data Use Authorization 2)
The brief allows an AI service only if it is "included in the authorized list published before Day 0", and
the rule covers coding assistants. Claude is approved on Logan's word (WORKLOG DEC-05), and every AI model
used so far is a Claude model (first two rows below). Where the list was published, and when, is not yet
recorded. The question is drafted in [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md); the answer's source and
date go here when it comes.

## Installed or already present on the laptop
| Software | Version | Licence | Origin | Purpose | Ships | Status |
|---|---|---|---|---|---|---|
| Claude Fable 5.1 (Claude Code desktop) | claude-fable-5-1 | service | Anthropic, US | coding assistant, docs drafting, research | no (declared) | in use, approved by Logan for the event (DEC-05) |
| Claude Opus 5.5 (Claude Code desktop) | claude-opus-5-5 | service | Anthropic, US | coding assistant, brainstorming, docs drafting; switched in by Logan 2026-10-16 ~22:40 CDT | no (declared) | in use, approved (DEC-05) |
| uv | present | MIT / Apache-2.0 | Astral, US | Python version + dependency manager | no (dev) | present |
| Python | 3.12.15 via uv for the project; 3.14.4 system unused | PSF | PSF | runtime | yes | in use since Fri 21:40 PDT, pinned in `.python-version` |
| git | present | GPL-2.0 | — | version control | no | present |
| GitHub CLI (gh) | present | MIT | GitHub | repo access | no | present, signed in as GhostWalka |
| Docker | present | Apache-2.0 | Docker Inc. | not planned | no | unused |
| PyYAML | 6.0.3 | MIT | PyYAML team | read assumptions, cards, priority files | yes | installed Fri 21:40 PDT into the project `.venv` |
| jsonschema (+ attrs, referencing, rpds-py, jsonschema-specifications, typing-extensions) | 4.26.0 | MIT (deps MIT; typing-extensions PSF-2.0) | Julian Berman et al. | validate guest manifests | yes | installed Fri 21:40 PDT |
| pytest (+ iniconfig, packaging, pluggy, pygments) | 9.1.1 | MIT (deps MIT / Apache-2.0 / BSD-2) | pytest devs | tests | no (dev) | installed Fri 21:40 PDT |
| hatchling | build backend, fetched by uv into an isolated build env | MIT | PyPA | builds the `sdv-governor` package | no (build) | used by `uv sync` |
| OpenCV (opencv-python-headless) and NumPy | 5.0.0.93 and 2.5.3 | Apache-2.0; BSD-3 | OpenCV.org; NumPy devs | CPU timing benches by a camera research agent, Fri about 23:30 PDT, on synthetic frames | no | nothing installed: both were already in the laptop's uv cache from Oct 9 and were used through PYTHONPATH; the project environment is unchanged |
| LibreOffice | 26.2.6.3 (system package) | MPL-2.0 | The Document Foundation | page-count renders of the Scenario C memo and README by a requirements agent, Sat about 00:20 PDT; now the fallback route in `tools/build_pdfs.py` | no | nothing installed: already on the system; the early renders went to /tmp |
| poppler-utils (`pdfinfo`) | 26.01.0-2ubuntu0.2 (system package) | GPL-2.0 or GPL-3.0 | Poppler developers, built by Ubuntu | page counts in `tools/build_pdfs.py` | no (dev) | nothing installed: already on the system |
| adb (Android Debug Bridge) | 1:34.0.5-12build1, Ubuntu universe | Apache-2.0 | AOSP source, built by Ubuntu | headless shell and port forwarding to node B over USB-C | no (dev); the USB link may carry the demo's wired path (DEF-01) | installed Sat 11:07 PDT at Logan's request; Logan typed sudo |
| pandoc | 3.7.0.2+ds-1, Ubuntu universe | GPL-2.0-or-later | John MacFarlane et al., Ubuntu | Markdown to HTML for the deliverable PDFs (`tools/build_pdfs.py`) | no (dev) | installed Sat 11:47 PDT at Logan's request; Logan typed sudo |
| Chromium (snap) | 155.0.8059.79 | BSD-3-Clause and others (Chromium licences) | Canonical snap of the Chromium project | headless print of the deliverable PDFs (`tools/build_pdfs.py`) | no (dev) | installed Sat 11:47 PDT at Logan's request |
| android-sdk-platform-tools-common | 28.0.2+12, Ubuntu universe | Apache-2.0 | AOSP, Ubuntu | udev rules giving USB access without root | no | installed Sat 11:07 PDT with adb |
| Superpowers plugin for Claude Code (obra/superpowers) | 6.4.2 | MIT | Jesse Vincent, Anthropic plugin directory (partner tier) | development workflow skills: TDD, plans, debugging, verification, subagent-driven development | no (dev) | install card shown to Logan Fri 21:36 PDT |

## Present on node B (VENTUNO Q `training05`); nothing installed by us
Survey Sat 11:12 PDT; details in [NODE_B_BOARD.md](NODE_B_BOARD.md).
| Software | Version | Licence | Purpose | Ships | Status |
|---|---|---|---|---|---|
| Ubuntu | 24.04.4 LTS, kernel 6.8.0-1084-qcom | mixed open source | board OS | yes (runs node B) | preinstalled by the organizers |
| Python | 3.12.3 | PSF | node B runtime | yes | preinstalled |
| PyYAML, jsonschema | system packages | MIT | cards and assumptions | yes | preinstalled |
| git, Docker, OpenSSH, NetworkManager | system packages | GPL-2.0, Apache-2.0, BSD, GPL-2.0 | repo copy, network | no | preinstalled; Docker unused |
| arduino-app-cli | preinstalled | not checked | Arduino App Lab back end | no | preinstalled; unused by us |
| Echo server for link timing | our own, 15 lines | ours | measure USB and Wi-Fi heartbeat round trips | no | ran Sat 11:14 PDT from /tmp, then removed |

## Planned (approved by Logan, DEC-39; added to the table above when actually installed)
| Software | Licence | Origin | Purpose | Ships | When |
|---|---|---|---|---|---|
| FastAPI | MIT | Sebastián Ramírez | HTTP and websocket server for the screen | yes | approved now (DEC-39) |
| uvicorn | BSD-3 | Encode | ASGI server | yes | approved now (DEC-39) |
| websockets | BSD-3 | Aymeric Augustin | inter-node bus and browser push | yes | approved now (DEC-39) |
| opencv-python-headless | Apache-2.0 (OpenCV); MIT packaging; the wheel bundles FFmpeg under LGPL-2.1 (its LICENSE-3RD-PARTY.txt) | OpenCV.org | camera capture and frame handling for the equipment watch | yes, if the camera line ships | when the camera step starts (DEC-39) |
| onnxruntime | MIT | Microsoft | runs any detector model on node B's CPU; no proprietary NPU runtime (DEC-31) | yes, if a model ships | when the node B step starts (DEC-39) |

Their transitive dependencies (for example pydantic and Starlette under FastAPI, NumPy under the last two)
are logged with versions and licences in the installed table at install time, as for jsonschema.

## Planned under earlier decisions (DEC-02, DEC-04)
| Item | Licence | Origin | Purpose | Ships | Decision |
|---|---|---|---|---|---|
| three.js (one vendored file) | MIT | three.js authors | 3D ship view, a toggle beside the scored 2D screen | yes, if the 3D view is built | DEC-04; not downloaded yet |
| Crew-rule grammar | ours | our own code; parser library not chosen | crew rules entered through an approved grammar, with no LLM-written code | yes, if built | DEC-02 |

## Considered, not approved
Named in planning documents but covered by no approval. Nothing here is installed or downloaded; each
needs Logan's approval before it is.
| Software or model | Licence | Origin | Considered for | Note |
|---|---|---|---|---|
| pydantic | MIT | Pydantic Services | manifest and rule models | arrives as a FastAPI dependency (DEC-39); not approved as a direct dependency of the core |
| Lark | MIT | Erez Shinan | parser for the crew-rule grammar (DEC-02) | the grammar is approved, the library is not |
| NumPy | BSD-3 | NumPy devs | ledger math | arrives as a dependency of opencv-python-headless and onnxruntime; not approved for the core |
| httpx | BSD-3 | Encode | one-time Open-Meteo Marine fetch, cached | dev only |
| torch + torchvision | BSD-3 | Meta | SSDlite320-MobileNetV3 person detector, COCO weights | models run with ONNX Runtime (DEC-31); person detection is last and optional (DEC-23) |
| MediaPipe EfficientDet-Lite0 | Apache-2.0 code; weights licence unconfirmed | Google | detector on node B | needs a TFLite runtime, not ONNX Runtime (DEC-31) |
| opencv-python (full build) | Apache-2.0 | OpenCV.org | webcam capture | DEC-39 approves the headless build instead |
| OR-Tools | Apache-2.0 | Google | optional solver for D2 placement | exhaustive search is the plan (GAMEPLAN) |
| ReportLab or WeasyPrint | BSD-3 | ReportLab Inc.; Kozea | memo and Physical Account to PDF | the PDF route is `tools/build_pdfs.py` instead |
| Phi-4-mini or Mistral-7B-Instruct | MIT / Apache-2.0 | Microsoft / Mistral AI | offline paraphrase of free text into rule-grammar text | not in the build plan |

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
| SeaDronesSee, MaSTr1325 | CC0, CC BY 4.0 | optional |

## Excluded on purpose
| Software | Reason |
|---|---|
| Ultralytics YOLO | AGPL-3.0 would bind the whole served application |
| Llama, Gemma | community licences are not OSI open source |
| Any model from a China-based company or derived from one (Qwen, DeepSeek, Yi, GLM, YOLOX, YOLOv6, YOLOv10, RT-DETR, D-FINE, LW-DETR, DAMO-YOLO, PP-YOLO, PaddleOCR) | brief, Data Use Authorization §2 |
| RF-DETR (Roboflow) | built on LW-DETR from Baidu; excluded as China-derived |
| OpenCV `wechat_qrcode` module | CNN models contributed by Tencent; use `cv2.QRCodeDetector` or zxing-cpp |
| DeepShip dataset | China origin (NWPU); same source audio available from Ocean Networks Canada |
| Node / React | no build step wanted; nothing installed; vanilla JS + vendored libs run offline |
| Any cloud inference or training | Logan's rule: runtime compute local only (DEC-01) |
| Qualcomm AI Hub, Edge Impulse | cloud compile and training; models stay local (DEC-31) |
| Qualcomm QAIRT SDK (proprietary NPU runtime) | not used unless the organizers clear it (DEC-31); models run with ONNX Runtime on node B's CPU |
| Datasets: CWRU, Paderborn, FuelCast, CRAWDAD, DeepShip, XJTU-SY, HUST, FLIR ADAS, Girona caves | no licence, non-commercial, no redistribution, or China origin |
