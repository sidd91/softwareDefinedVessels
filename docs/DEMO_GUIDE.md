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

## The run: press play, about 1 minute, no clicks during it

1. **Quick tour, 15 seconds (OPERATIONS tab).** Point at the ship drawing, the eight boxes under it, and the panel on
   the right. All three are on the first screen, so do not scroll. Say: "This is what the crew sees: the ship, its equipment, its budget, and every decision with its reason."
2. **Click DEMO COMPARE** (last tab at the top). Survey is on the left, rescue on the right. The whole run fits on this one screen, no scrolling.
3. **In the bottom bar click ×20, then RESTART.** The 20-minute mission now plays out in 1 minute by itself. Do not click
   anything else. At each event a red or amber alert box opens at the top of each column, saying in one or two
   sentences what happened and what ArgOS did. Talk over it:

| About | What appears in both columns | Say |
|---|---|---|
| 0:24 | Minute 8: the drone is low on battery | "The drone must land. Survey pauses the underwater robot. Rescue cancels its dive and saves power for the drone." |
| 0:36 | Minute 12: a generator cuts out | "Both missions still fit on one generator, so nothing is turned off." |
| 0:57 | Minute 19: a cooling pump fails | "Now something must give. Survey slows the drone's charging. Rescue turns the communications unit down. Same ship, same failure, the mission decides what gives way first." |
| 1:00 | The clock stops at T+00:20:00 | "That is graceful degradation, decided by the mission." |

At minute 19 the two alerts show the difference: survey slows the drone's charging, rescue turns the communications unit down.

**If anything goes wrong:** click RESTART in the bottom bar. The run starts again from zero at the same speed.

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
| ALARM / CAUTION | red: ArgOS had to act. Amber: the ship coped, nothing turned down |
| ARMED | ready to happen if needed |
| EXECUTED | done |
| LIMIT | what the ship can supply, minus a small safety margin |
