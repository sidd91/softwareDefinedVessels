# ArgOS demo guide (operations screen)

One person drives and speaks. The run takes 2 minutes at most. The screen is the operations screen at http://127.0.0.1:8000/.
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

## The run: 2 minutes, hard stop

The bottom bar has the buttons: HOLD, PACE, JUMP (G4 LOW BATT, GEN 2 TRIP, CHW P1 TRIP), RESTART, PRIORITY SURVEY / RESCUE.
Decisions appear in the panel on the right. Its first line says what was decided. Its last two rows, PRIORITY and
CREW RULE, show the rules in force. Keep each line short and move on. You do not need to wait for the clock.

| By | Do | Point at | Say |
|---|---|---|---|
| 0:10 | Ask: "Rescue first, or survey first?" Click their pick (RESCUE or SURVEY), then RESTART | Top left: MISSION RESCUE (or SURVEY) | "Same software, your priorities." |
| 0:30 | Click G4 LOW BATT | The right panel, first line | "Minute 8. The drone is low on battery and must land. The robot needs the ship slow, the drone needs it moving. ArgOS lands the drone first, in under a millisecond." |
| 0:50 | Click GEN 2 TRIP | The POWER box | "Minute 12. A generator cuts out. Everything still fits on the other one, so nothing is turned off." |
| 1:15 | Click CHW P1 TRIP | INJECTED in the right panel, then the COOLING box | "Minute 19. We break a cooling pump on purpose. ArgOS turns one thing down within the 5-second rule, and says why." |
| 1:40 | Click DEMO COMPARE (last in the top menu) | The two columns | "Same failure, two priorities, two different answers. Survey slows the drone's charging. Rescue protects the drone." |
| 2:00 | Stop | | "That is ArgOS." |

If you are running long, skip the GEN 2 TRIP step. If the jury picked SURVEY at minute 8, say "the robot waits
underwater" instead of anything about rescue.

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
