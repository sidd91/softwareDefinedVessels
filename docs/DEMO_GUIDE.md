# ArgOS demo guide (operations screen)

One person drives and speaks. Total about 2 minutes. The screen is the operations screen at http://127.0.0.1:8000/.
Click each button once. A pause of up to a second after a click is normal.

## Setup, 30 minutes before

1. Open the Terminal. Type each line and press Enter:
   ```
   cd ~/softwareDefinedVessels
   git pull
   uv sync
   uv run sdv demo
   ```
   Good: the last line printed reads "ArgOS screen on http://127.0.0.1:8000/ (live)". Leave this window open.
2. Open Chrome and go to `127.0.0.1:8000`. Good: LINK UP at the top right and the clock counting.
3. Press F11 for full screen. Zoom to 125 % (Ctrl and +). Turn on Do Not Disturb.
4. Practise the run below once. Then click RESTART and leave it running.

Use only one browser tab. A second tab runs its own separate copy of the demo.

## The run

The bottom bar has the buttons: HOLD, PACE, JUMP (G4 LOW BATT, GEN 2 TRIP, CHW P1 TRIP), RESTART, PRIORITY SURVEY / RESCUE.
Decisions appear in the panel on the right. Its first line says what was decided.

| Step | Do | Point at | Say |
|---|---|---|---|
| 1 | Ask the jury: "Should this ship put rescue first, or the survey first?" Click RESCUE or SURVEY in the bottom bar | Top left: MISSION RESCUE (or SURVEY) | "You chose rescue. Same software, different priorities." |
| 2 | Click RESTART | The eight boxes under the ship drawing | "A 60-metre ship carrying a drone, an underwater robot, a radio sensor and a communications unit. These boxes are its budget: power, cooling, deck, weight and more." |
| 3 | Click G4 LOW BATT (jumps to minute 8) | The right panel, first line, then LAND BY | "Minute 8. The drone is down to 18 % battery and must land within 12 minutes. The robot needs the ship slow and steady, the drone needs it moving. ArgOS lands the drone first, and it decided in under a thousandth of a second." |
| 4 | When you finish talking, click GEN 2 TRIP (minute 12) | The POWER box (amber), then the SHED ORDER list | "Minute 12. One generator cuts out. Everything still fits on the other one, so nothing is turned off. The list shows what would be turned down first if needed." |
| 5 | When you finish talking, click CHW P1 TRIP (minute 19) | INJECTED on the right panel, then the COOLING box | "Minute 19. We break a cooling pump on purpose. The equipment now needs more cooling than is left, so ArgOS turns one thing down. The rules allow 5 seconds. It took under a millisecond." |
| 6 | Nothing. The clock stops at T+00:20:00 | The right panel | "Three problems in 20 minutes. Each time ArgOS decided at once and wrote down why." |
| 7 | Click MISSION COMPARE (top menu). On the timeline click 00:19 | The two columns side by side | "Same ship, same failure, two priorities. Survey slows the drone's charging. Rescue protects the drone and turns the communications unit down instead." |

What changes with the jury's choice:

| Moment | If RESCUE | If SURVEY |
|---|---|---|
| Minute 8 | "The robot's survey is cancelled, and power is kept free to charge the drone." | "The robot waits underwater and loses about 25 minutes of survey." |
| Minute 12 | "82.5 of 95 kW in use, 12.5 spare." | "49.5 of 95 kW in use, 45.5 spare." |
| Minute 19 | "The communications unit drops to low power." | "The drone charges more slowly." |

Optional, drop it if time is short: "With fewer people aboard, the same rules change. At 6 aboard the drone only lands
under a plan agreed in advance, and with nobody aboard the deck must already be checked clear."

## If something goes wrong

- **The clock is stopped and HOLD reads RUN:** press Space. At T+00:20:00 the run is simply over.
- **Top right says LINK DOWN:** in the Terminal press Ctrl and C, then type `uv run sdv demo` and press Enter. The page
  comes back by itself after a few seconds.
- **Wrong choice at the top left:** click the right PRIORITY button, then RESTART.
- **"Address already in use" when starting:** type `uv run sdv demo --port 8010` and open `127.0.0.1:8010`.
- **The page looks wrong:** press Ctrl, Shift and R. It restarts on SURVEY, so pick again and click RESTART.
- **Nothing works:** in the Terminal press Ctrl and C, then type `uv run sdv demo --source fixtures`. This plays a
  recording of the same run, marked REPLAY. Say: "We'll show you a recording of the same run."

## A few words on the screen

| On screen | Means |
|---|---|
| G1, G3, G4, G5 | radio sensor, underwater robot, drone, communications unit |
| CHW | chilled water, the ship's cooling |
| HOLDS | the load fits, nothing changes |
| SHED | turn a piece of equipment down to free power or cooling |
| ARMED | ready to happen if needed |
| EXECUTED | done |
| INJECTED | a failure we add on purpose |
| LIMIT | what the ship can supply, minus a small safety margin |
