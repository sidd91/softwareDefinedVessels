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
2. Open a new Chrome Incognito window (Ctrl, Shift and N) and go to `127.0.0.1:8000`. Incognito makes sure you see the
   latest screen, not an old saved copy. Good: LINK UP at the top right and the clock counting.
3. Press F11 for full screen. Zoom to 125 % (Ctrl and +). Turn on Do Not Disturb.
4. Practise the run below once. Then click RESTART and leave it running.

Use only one browser tab. A second tab runs its own separate copy of the demo.

## The run: 2 minutes, hard stop

Buttons used: RESTART and the three event buttons in the bottom bar (G4 LOW BATT, GEN 2 TRIP, CHW P1 TRIP), and the
OPERATIONS and DEMO COMPARE tabs at the top. Click each once. You do not need to wait for the clock.

| By | Click | Point at | Say |
|---|---|---|---|
| 0:15 | Nothing yet (you are on OPERATIONS) | The ship drawing, then the eight boxes under it | "This is what the crew sees: the ship, its equipment, and its budget of power, cooling, space and weight." |
| 0:25 | RESTART, then DEMO COMPARE (last tab at the top) | The two columns | "The same ship under two missions, side by side. Survey on the left, rescue on the right." |
| 0:50 | G4 LOW BATT | Both columns, first line | "Minute 8. The drone is low on battery. Both missions land it first. Survey pauses the underwater robot. Rescue cancels the robot's dive and saves power for the drone." |
| 1:05 | GEN 2 TRIP | Both columns | "Minute 12. A generator cuts out. Everything still fits, so neither mission turns anything off." |
| 1:30 | CHW P1 TRIP | Both columns, then the table underneath | "Minute 19. A cooling pump fails. Survey slows the drone's charging. Rescue turns the communications unit down instead. Each decided within the 5-second rule." |
| 1:50 | OPERATIONS | The right panel: first line, then PRIORITY and CREW RULE | "Every decision comes with its reason and the rules in force." |
| 2:00 | Stop | | "That is ArgOS." |

If you are running long, skip GEN 2 TRIP.

## If something goes wrong

- **The clock is stopped and HOLD reads RUN:** press Space. At T+00:20:00 the run is simply over.
- **Top right says LINK DOWN:** in the Terminal press Ctrl and C, then type `uv run sdv demo` and press Enter. The page
  comes back by itself after a few seconds.
- **Wrong choice at the top left:** click the right PRIORITY button, then RESTART.
- **"Address already in use" when starting:** type `uv run sdv demo --port 8010` and open `127.0.0.1:8010`.
- **DEMO COMPARE shows a TIMELINE box, or the right panel shows long paragraphs:** that is an old saved copy. Close
  the window and open `127.0.0.1:8000` in a new Incognito window.
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
