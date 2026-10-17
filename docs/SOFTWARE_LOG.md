# Software and AI usage log

Every tool, package, model and service used on this project, dev-time or shipped. Kept current as
things are added. "Ships" means it is in the deliverable repo or runs during the live demo.
Policy: open-source third-party code only (OSI licence, no AGPL), or our own; every AI model declared.

## Needs action from Logan
| Item | Why | Status |
|---|---|---|
| `gh auth login` as GhostWalka | team repo is private | done Fri 20:40 PDT |

## Installed or already present on the laptop
| Software | Version | Licence | Origin | Purpose | Ships | Status |
|---|---|---|---|---|---|---|
| Claude Fable 5.1 (Claude Code desktop) | claude-fable-5-1 | service | Anthropic, US | coding assistant, docs drafting, research | no (declared) | in use, approved by Logan for hackathon |
| Claude Opus 5.5 (Claude Code desktop) | claude-opus-5-5 | service | Anthropic, US | coding assistant, brainstorming, docs drafting; switched in by Logan 2026-10-16 ~22:40 CDT | no (declared) | in use, approved |
| uv | present | MIT / Apache-2.0 | Astral, US | Python version + dependency manager | no (dev) | present |
| Python | 3.12.15 via uv for the project; 3.14.4 system unused | PSF | PSF | runtime | yes | in use since Fri 21:40 PDT, pinned in `.python-version` |
| git | present | GPL-2.0 | — | version control | no | present |
| GitHub CLI (gh) | present | MIT | GitHub | repo access | no | present, signed in as GhostWalka |
| Docker | present | Apache-2.0 | Docker Inc. | not planned | no | unused |
| PyYAML | 6.0.3 | MIT | PyYAML team | read assumptions, cards, priority files | yes | installed Fri 21:40 PDT into the project `.venv` |
| jsonschema (+ attrs, referencing, rpds-py, jsonschema-specifications, typing-extensions) | 4.26.0 | MIT (deps MIT / Apache-2.0) | Julian Berman et al. | validate guest manifests | yes | installed Fri 21:40 PDT |
| pytest (+ iniconfig, packaging, pluggy, pygments) | 9.1.1 | MIT (deps MIT / Apache-2.0 / BSD-2) | pytest devs | tests | no (dev) | installed Fri 21:40 PDT |
| hatchling | build backend, fetched by uv into an isolated build env | MIT | PyPA | builds the `sdv-governor` package | no (build) | used by `uv sync` |
| OpenCV (opencv-python-headless) and NumPy | 5.0.0.93 and 2.5.3 | Apache-2.0; BSD-3 | OpenCV.org; NumPy devs | CPU timing benches by a camera research agent, Fri about 23:30 PDT, on synthetic frames | no | nothing installed: both were already in the laptop's uv cache from Oct 9 and were used through PYTHONPATH; the project environment is unchanged |
| Superpowers plugin for Claude Code (obra/superpowers) | 6.4.2 | MIT | Jesse Vincent, Anthropic plugin directory (partner tier) | development workflow skills: TDD, plans, debugging, verification, subagent-driven development | no (dev) | install card shown to Logan Fri 21:36 PDT |

## Planned (added to the table above when actually installed)
| Software | Licence | Origin | Purpose | Ships |
|---|---|---|---|---|
| FastAPI | MIT | Sebastián Ramírez | HTTP + websocket server for the screen | yes |
| uvicorn | BSD-3 | Encode | ASGI server | yes |
| websockets | BSD-3 | Aymeric Augustin | inter-node bus + browser push | yes |
| pydantic | MIT | Pydantic Services | manifest and rule models | yes |
| Lark | MIT | Erez Shinan | controlled-natural-language rule grammar | yes |
| numpy | BSD-3 | NumPy devs | ledger math | yes |
| httpx | BSD-3 | Encode | one-time Open-Meteo Marine fetch, cached | no (dev) |
| torch + torchvision | BSD-3 | Meta | SSDlite320-MobileNetV3 detector, COCO weights | yes |
| opencv-python | Apache-2.0 | OpenCV | webcam capture, frame handling | yes |
| three.js (vendored file) | MIT | three.js authors | 3D ship view | yes |
| ReportLab or WeasyPrint | BSD-3 | — | memo and Physical Account to PDF | no (dev) |
| Phi-4-mini or Mistral-7B-Instruct (optional) | MIT / Apache-2.0 | Microsoft / Mistral AI | offline paraphrase of free text into rule grammar | only if used, declared |

## Data sources (planned; none downloaded yet)
Full tiered list with sizes in `research/SENSOR_CATALOG.md`. Each is declared here when pulled.
| Source | Licence | Status |
|---|---|---|
| Open-Meteo Marine and Archive | CC BY 4.0, free tier non-commercial | planned, organizer check pending |
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
| Any cloud inference or training | Logan's rule: runtime compute local only |
| Qualcomm QAIRT SDK and AI Hub | proprietary runtime and cloud compile; only with organizer approval |
| Datasets: CWRU, Paderborn, FuelCast, CRAWDAD, DeepShip, XJTU-SY, HUST, FLIR ADAS, Girona caves | no licence, non-commercial, no redistribution, or China origin |
