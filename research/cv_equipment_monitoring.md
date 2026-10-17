# Camera-based equipment monitoring (draft for team review)

Status: draft, Fri 23:55 PDT. Drafted by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka) from a
seven-agent research workflow with licence and feasibility checks (26 findings, all applied). Research
and design only; nothing is built.

## 1. Direction

- Cameras watch **equipment**: leaks, smoke or small flames, and fixed gear that is damaged or out of
  place, where other sensors are missing or slow (WORKLOG DEC-23).
- Cameras are **optional supply, not the hero** (DEC-27). We cannot assume a ship has them, so the
  governor works exactly the same with none. Where a camera exists, it turns a late or unknown signal
  into an early, explained one.
- In the demo the camera appears as **one breadth line**: the cooling-loop leak (C1). The deep demo
  examples are Scenarios A and B (DEC-26). C2 and C3 below are design depth for the team, not demo beats.
- Person detection of any kind is optional and last (section 7).

Worked examples are numbered C1 to C3 so they never collide with the brief's decision classes D1 to D6.

## 2. Breadth catalogue

Coverage comes from [2]; where it says sometimes, a portable camera can join as a guest [1]. Rows not
shown live are replayed from the synthetic `cam_detection_stream` [6] and labelled "replayed" on screen.

| Use case | Where | Why a camera | Method | Governor effect | Fixed camera usual? | Tier |
|---|---|---|---|---|---|---|
| Chilled-water leak | Pump, bay manifold | Flow measured only sometimes [4]; makeup water hides small leaks (land practice) [14] | Growing wet area | Cooling planned as degraded | Machinery yes (naval); bays sometimes | demo breadth line |
| Smoke or small flame | Drone charger, hangar | Zone detectors wait 10-60 s for smoke (estimate) [4]; Li-ion fires need early detection [15] | Edge loss; flame flicker | G4 charge off; zone hazard | Sometimes | design |
| Gear out of place on the landing zone | Flight deck | Only a human sweep checks it [5] | Tags against the last sweep | R3 recovery hold (Scenario C memo) [7] | Naval with helo: one PTZ | design |
| Manual valve or gauge with no data link | Cooling cross-connect | Manual line-ups are invisible to automation [5] | Tag angle; needle reading | Standby cooling credited or not | Machinery yes | design; valve tag is the cheapest live extra |
| Oil or hydraulic leak near hot surfaces | Genset, winch | Over a third of ship fires start in engine rooms, often oil on hot surfaces [13]; hydraulic oil sank Viking Victor [16] | Leak check | Genset at risk: admit as one set down [4]; winch work refused | Machinery yes; deck sometimes | design |
| Deck machinery not stowed | Crane, A-frame, davit | Limit switches fail or stay unreset [5] | Tag against stowed pose | G4 recovery and G3 ramp work held | Sometimes | design |
| Door or hatch open while its switch says shut | Ramp, hatches | SOLAS accepts TV for ro-ro door leaks [17]; a doubtful switch means open [4] | Tag or region change | Ramp not free | Ro-ro yes; naval sometimes | design |
| Water at shaft seals or a bay floor | Machinery, bays | Bilge floats trip late or jam [4]; Helge Ingstad flooded via its shafts [5] | Wet-area growth | Hold deck work, freeze mass | Machinery yes | design |
| Hot spot | Cable lugs, exhausts | Colour cameras see glow only above about 525 °C [21] | Thermal camera; synthetic only | Zone pre-alarm | Naval: often LWIR [2] | design |
| Untagged damage, missing lashing | Any view | Nothing else looks | PaDiM heatmap; tags | Crew check only | n/a | later |

## 3. Worked examples

Guest set G1, G3, G4, G5 (9.56 t, under the 10 t margin) [8]; seawater 24 °C as in Scenario B [10].
Scores shown are a **confidence index (uncalibrated)**, illustrative until we measure on real frames.

### C1. Chilled-water leak: cooling planned as degraded (the demo breadth line)

- **Trigger.** The camera sees a darker, blue-tinted wet area grow from under chilled-water pump 1 over
  10 to 60 s, with anchors visible and self-checks passed. The reading maps to the existing cooling
  state `degraded`, tagged `source: camera, confirmed: false`; no new state value is added.
- **Decision.** At 24 °C the loop rejects about 133 kW, 80 kW if degraded (x0.6); G3 charging, G4 fast
  charge and G5 put 105 kW on it (25 + 35 + 45) [10]. On camera evidence alone the governor **plans** as
  degraded: admission and placement use 75 kW (80 less 5 kW headroom), nothing new starts on the loop,
  and the shedding ladder is armed. It **sheds only on a confirmed fault**, a pump alarm or a crew
  report, per sensor rule 4 [3]. Under the rescue priority file the armed step is G5 to 8 kW, freeing
  37 kW, while loop inertia (+30 kW for 60 s) covers the gap [10].
- **Sentence.** "Cooling planned as degraded: camera sees a growing leak under chilled-water pump 1
  (index 0.81, uncalibrated, 0.5 s old); a degraded loop at 24 °C rejects 80 kW against 105 kW of
  guests, so nothing new starts on the loop and G5 drops to low power on a confirmed pump fault."
- **When the camera is unknown.** The leak field shows "unknown" on screen and cooling planning falls
  back to plant sensors, where pump status unknown already counts as degraded [3]. This is a deliberate
  exception to "camera unknown means changed", recorded in the Physical Account.
- **Demo.** One webcam, and the growth window is longer than a breadth line, so C1 is shown from the
  replayed stream by default. It goes live only if the tray fits in the same webcam frame as any other
  live region, with its own region and reference.
- **Safe prop, if live.** A white or light paper towel on a tray beside a printed pump; 10 to 20 ml of
  blue-dyed water by pipette from the source edge; the check also requires blue hue so shadows and
  hands do not read as leaks. Lock exposure and white balance if the webcam allows (unconfirmed) and
  retake the reference just before the demo.

### C2. Smoke or small flame at the drone charger (design only)

- **Trigger.** Over G4's battery: edge energy and saturation fall while other tiles stay sharp (smoke)
  [19], or fire-coloured pixels flicker near 10 Hz at 30 fps (flame) [18][20]. Thermal sees heating
  sooner (FIRESAFE II detected an 80 kW fire at about 50 m) but our webcam has none, so thermal is
  synthetic only [12].
- **Whole view degrading.** If every tile degrades together over a few seconds, not in one frame, the
  reading is "possible smoke or lens fault" and is treated as a hazard, never as a camera fault alone.
- **Unknown.** An unknown flight-deck hazard suspends new flight-deck admissions and raises a crew check.
- **Latching.** Smoke, flame and leak findings stay until crew or the plant confirms; they never clear
  themselves when the haze drifts.
- **Decision, two options for the team.** (a) Turn off G4's 35 kW charge at once on camera smoke, within
  the 5 s first-action ceiling; or (b) arm that step, suspend flight-deck admissions and wait for the
  fire panel or crew, as rule 4 does for plant faults [3]. Either way the governor only asks crew or the
  PMS to isolate the charger; it never commands firefighting and never sheds fire detection or pumps
  (research R-E9-1, R-E9-3) [5].
- **Sentence (either option).** "G4 charging {stopped | armed to stop}: camera sees haze over the drone
  battery while the rest of its view is sharp (index 0.7, uncalibrated, 0.4 s old); flight deck closed
  to new work until crew acknowledge."
- **Prop if ever shown.** Grey tracing paper slid over a printed battery. The flame check stays
  replay-only unless it works on the actual prop and webcam frame rate by Sat midday; cheap LED candles
  often flicker below 10 Hz and venue lighting can alias into the band. No fog, vapes, incense or flame.

### C3. Gear out of place on the landing zone (design only; feeds the Scenario C memo)

- **Trigger.** Two checks over the taped landing zone: deck markers FD-1 to FD-4 and a tagged fitting
  against their saved positions, and a whole-zone region check against the fixed reference, so a box
  dropped between markers is caught too. A hidden anchor or a slewed camera means unknown, which holds.
- **Decision.** R3 holds clearance to land within 200 ms **of the detection event**; the camera itself
  adds up to about 1.5 s (2 Hz with N-of-M debounce) [7][10]. Only deck-occupancy findings may withdraw
  themselves after fresh in-view checks; hazard findings latch (C2).
- **Sentence (templated).** "Recovery held: {item} in the landing zone (index {i}, uncalibrated,
  {age} s old); G4 at {pct} % must land in about {t} min, and confirm plus clear takes up to {x} min at
  {crew} aboard."

## 4. Methods and camera self-checks

Per camera at 2 Hz: self-checks, alignment to a fixed reference, region checks, debounce (N of M),
event [3]. References stay fixed because OpenCV's adaptive background model (MOG2) absorbs anything
still, puddles included [22]. Per-check timings were measured by a research agent on this laptop's CPU
with synthetic frames [11]. The end-to-end loop on the live webcam is **not measured** and the Qualcomm
box is untested: a 5-minute webcam soak on Sat morning should log the real frame rate.

Align first. Unaligned, a 2 px shake changed 4.9 % of a region, more than a real 40x40 px object
(3.1 %); a 30 % brightness step flagged 99.5 % by raw difference. Phase-correlation alignment (2.9 ms)
with a normalised difference removed both and kept the object [11].

| Check | Method | Measured (synthetic) | False triggers at sea | Unknown when |
|---|---|---|---|---|
| Item moved, valve handle, gear stowed, deck markers | AprilTag 36h11 (in OpenCV) on the item, pose against two anchor tags | 8 tags at 1280x720: 3.6 ms; rotation error up to 0.5 ° | glare, salt film, roll blur, something in front | anchor unseen |
| Zone clutter | aligned normalised difference over a whole region | under 3 ms | shadows, wash water | view moved |
| Leak | darker, blue-tinted area joined to the source, growing over 10-60 s | 0.3 ms | deck wash, rain, footprints | occluded |
| Smoke | edge-energy drop and greying [19] | 0.6 ms | steam, spray, fog | latches as possible smoke if all tiles drop over seconds |
| Small flame | YCrCb colour rule [20] plus 10 Hz flicker by FFT over 64 frames [18] | 1.0 ms | orange light, glints, beacons, LED aliasing | under 20 fps |
| Gauge needle | HoughCircles, then Hough needle line [23] | 2.7 ms; 0.7-2.7 ° error on synthetic gauges only | glare, viewing angle | no needle |

A tag on a valve handle is the cheapest live extra. Reading a real needle needs per-gauge calibration
and is unmeasured on the webcam.

| Self-check | Method | Measured | On fail |
|---|---|---|---|
| Blur, obstruction, exposure | Laplacian variance per tile against setup; histogram | 0.6 ms | region unknown; all tiles over seconds: possible smoke or lens fault |
| Frozen | thumbnail difference near 0, frame counter stalled | 0.01 ms | camera unknown |
| View moved | phase correlation, missing anchors, ORB homography | 2.9 / 2.6 ms | realign if small, else unknown |

The confidence index is camera health x persistence x margin over threshold, uncalibrated, and is
labelled that way on screen and in the Physical Account. PaDiM (untagged damage) is a stretch with
unmeasured CPU time.

## 5. Models and datasets

C1 to C3 need no trained weights. Nothing is downloaded; each pull needs Logan's go-ahead [3].

| Item | Licence | Origin | Use and caveat |
|---|---|---|---|
| OpenCV (main modules, with ArUco and AprilTag), NumPy, scikit-image | Apache-2.0 [22]; BSD-3; BSD-3 | OpenCV.org with contributors worldwide, including a China team (library code, no weights); ArUco from Universidad de Córdoba, Spain; AprilTag code from the University of Michigan | All checks; no weights; exact replay |
| anomalib, PaDiM only | Apache-2.0 [24] | Intel; PaDiM from CEA List, France [25] | Stretch. Import PaDiM only: anomalib also bundles STFPM (Beihang, Baidu) and FastFlow (SenseTime), excluded, and newer models whose affiliations are likely China-based (unconfirmed), also excluded. Pulls PyTorch, Lightning (avoid 2.6.2 and 2.6.3, a known supply-chain compromise), torchmetrics, FrEIA, kornia, einops: pin versions and check each licence first. Export path in 2.7.0 unconfirmed |
| timm `resnet18.a1_in1k` (about 47 MB) | Apache-2.0 card [26] | timm weights (Hugging Face); ResNet architecture from Microsoft Research | PaDiM backbone; trained on ImageNet-1k, whose terms are non-commercial [27]: declare |
| ONNX Runtime | MIT | Microsoft, USA | Laptop and Qualcomm CPU, only if a model is used |
| D-Fire | CC0 1.0 [28] | GAIA and UFMG authors, Brazil; image sources not stated | Tests only the flame colour rule, for false positives on its 9,838 negatives; the smoke and flicker checks need video and stay tested on our own clips |
| Our own frames | ours | team | References and any PaDiM normal set |

Declare if used, not pulled by default: MVTec AD and LOCO AD (CC BY-NC-SA 4.0) [29]; MIVIA fire videos
(University of Salerno, no licence stated, partly web-sourced, request-page terms unseen) [30]. Leaks,
gauges and thermal stay synthetic; no trustworthy open leak dataset was found.

Excluded: Ultralytics-based models (AGPL), including Pyronear's YOLO models (card says Apache-2.0 but
built on Ultralytics), pedbrgs (YOLOv5) and the ETH gauge reader (Ultralytics and OpenMMLab MMOCR) [31][34];
China-origin or derived work: STFPM, FastFlow, RF-DETR, YOLOX, YOLOv6, RT-DETR, D-FINE, PP-YOLO, the
PaddlePaddle meter reader, FASDD (Wuhan University), `wechat_qrcode` (Tencent) [6][33]; sets with no
licence or undeclared training data (DeepQuestAI, Roboflow Universe spill and gauge sets, EdBianchi ViT
with an Apache-2.0 card but undeclared training data); CLIP (its card rules out deployed use) and
EfficientAD (ImageNet use per the paper body, unconfirmed) [33].

## 6. How detections enter the governor

Each camera is an inventory entry in `assumptions.yaml` naming its regions and the variable each feeds
[1]. Fixed ship cameras run in the 20 % ship-systems compute reserve [7]; a portable camera is admitted
as a guest [1]. A check logs a detection as a `sensor_reading` event, never a frame [9]:

```yaml
{seq: 4182, t_s: 612.5, type: sensor_reading, payload: {source: camera, camera: CAM-1,
 region: chw_pump1_tray, check: leak, state: alarm, score: 0.12, threshold: 0.10,
 confidence_index: 0.81, calibrated: false, age_s: 0.5, reference_age_s: 3600, latched: true,
 health: {blur_ok: true, frozen: false, view_ok: true}}}
```

- A pure function maps each reading into a conditions-snapshot field (`cooling`, `deck`, and a new
  `zone_hazard`) with source, age and confidence [9]. Replay needs no video and reproduces every
  decision [3]. `zone_hazard` and the reading fields above are additions to `docs/ARCHITECTURE.md`.
- Unknown never means safe: older than 3 s, or a failed self-check, is unknown [7]. Where the camera is
  the only sensor (deck, bays) unknown takes the conservative value; for cooling only the early warning
  is lost (C1).
- A camera adds hazards but never clears another sensor's alarm; the fire panel and bilge switches stay
  authoritative [3]. Hazard findings latch until crew or the plant confirms; only deck-occupancy
  findings withdraw themselves.
- Over a degraded link the edge node sends detections, never video [1].

## 7. Person detection: optional, last, nice-to-have

Only if everything above works: torchvision SSDlite (BSD-3 code; COCO detection weights on an
ImageNet-1k backbone, whose terms are non-commercial: declare) could count people per zone [6], with no
identities, faces, track IDs or stored frames. A count may add to the landing officer's report but
never clears a zone, and it is first on the cut list [1]. C3's zone check already flags anything new
on the landing zone, person or object.

## 8. Open questions for the team

1. C2: may camera-only smoke stop the drone's charge at once, or only arm the step until the fire panel
   or crew confirms?
2. Is G1, G3, G4, G5 our standard guest set? The brief's G2 to G5 is 13.0 t against the 10 t margin and
   needs Bay 2 twice [8][10].
3. Is PaDiM worth the PyTorch download and the ImageNet-weights declaration, and should we ask the
   organizers whether an architecture from a Microsoft lab in China raises the China-derived rule?
4. Do we bring a second USB camera or a phone camera so the C1 tray can be live beside another region?

## 9. Sources

Sources 1 to 9 are files in the team repo.

1. GAMEPLAN.md.
2. research/camera_placement.md.
3. research/SENSOR_CATALOG.md.
4. research/sensors/platform_power_thermal.md.
5. research/vessels/event_protocols_log.md (R-E9 rules, accident lessons).
6. research/sensors/payload_deck_human.md.
7. docs/SCENARIO_C_MEMO.md.
8. config/assumptions.yaml, manifests/G1-G6.yaml.
9. docs/ARCHITECTURE.md (event timeline, conditions snapshot).
10. Fincantieri challenge brief, Annexes A and B (local PDF).
11. Bench scripts written by a research agent (session scratchpad, not in the repo), run on synthetic frames with OpenCV 5.0 and NumPy already in the laptop's uv cache; not rerun on the webcam.
12. EMSA FIRESAFE II Part 4 (2018). https://www.emsa.europa.eu/publications/reports/download/5487/3424/23.html
13. IACS, low-pressure fuel pipe leaks (2019). https://www.intercargo.org/wp-content/uploads/2019/10/Fire-risks-low-P-fuel-pipes-by-IACS.pdf
14. Deppmann, makeup water leaks (2018). https://www.deppmann.com/wp-content/uploads/2018/07/RLD_MMM_Unhide_Makeup_Water_Leaks_Hydronic_Systems.pdf
15. IMCA SF 18/25 on USCG Safety Alert 14-25. https://www.imca-int.com/resources/safety/safety-flashes/1825-uscg-lithium-ion-battery-system-installations
16. MAIB, Viking Victor. https://www.gov.uk/maib-reports/fire-in-pump-room-on-standby-vessel-viking-victor-off-aberdeen-scotland-resulting-in-the-vessel-sinking
17. IMO MSC.11(55), SOLAS II-1/23-2, now 17-1 (numbering unconfirmed; search summary). https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.11(55).pdf
18. Töreyin et al., fire and flame detection. https://homepages.inf.ed.ac.uk/rbf/CVonline/LOCAL_COPIES/TOREYIN1
19. Töreyin, Dedeoğlu, Çetin, smoke detection, EUSIPCO 2005. https://repository.bilkent.edu.tr/items/a1830e53-10cc-4a88-aab6-4fa3a4734fb6
20. Celik and Demirel, Fire Safety Journal 44(2), 2009. https://firedoc.nist.gov/article/JngzXYQBWEcjUZEYezSu
21. Draper point. https://en.wikipedia.org/wiki/Draper_point
22. OpenCV licence and MOG2 header. https://github.com/opencv/opencv/blob/4.x/LICENSE ; https://raw.githubusercontent.com/opencv/opencv/4.x/modules/video/include/opencv2/video/background_segm.hpp
23. Intel analog gauge reader (MIT, archived). https://github.com/intel-iot-devkit/python-cv-samples/tree/master/examples/analog-gauge-reader
24. anomalib. https://github.com/open-edge-platform/anomalib
25. PaDiM https://arxiv.org/abs/2011.08785 ; PatchCore https://arxiv.org/abs/2106.08265
26. timm resnet18.a1_in1k. https://huggingface.co/timm/resnet18.a1_in1k
27. ImageNet terms. https://www.image-net.org/download.php
28. D-Fire. https://github.com/gaiasd/DFireDataset
29. MVTec LOCO AD. https://www.mvtec.com/company/research/datasets/mvtec-loco
30. MIVIA fire dataset. https://mivia.unisa.it/datasets/video-analysis-datasets/fire-detection-dataset/
31. ETH analog_gauge_reader. https://github.com/ethz-asl/analog_gauge_reader
32. STFPM https://arxiv.org/abs/2103.04257 ; FastFlow https://arxiv.org/abs/2111.07677
33. Exclusion checks: FASDD https://essd.copernicus.org/preprints/essd-2022-394/ ; OpenVINO meter reader https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/meter-reader ; CLIP card https://github.com/openai/CLIP/blob/main/model-card.md ; EdBianchi https://huggingface.co/EdBianchi/vit-fire-detection ; DeepQuestAI https://github.com/DeepQuestAI/Fire-Smoke-Dataset ; EfficientAD https://arxiv.org/abs/2303.14535
34. Ultralytics-based fire models excluded: https://huggingface.co/pyronear/yolov11s ; https://github.com/pedbrgs/Fire-Detection
