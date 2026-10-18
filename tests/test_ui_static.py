"""The page's own controls must survive the /ws stream (12 frames/s at x12, 60 at x60): a button that is rebuilt between
mousedown and mouseup never fires click, which is how the rehearsal lost 0 of 12 PRIORITY and JUMP presses at x12
while the static HOLD/RUN button took 10 of 10. So app.js paints the SIM-bar groups and the title-bar chips through
util.paint / util.paintEach, which touch the DOM only when the markup changed, and never assigns innerHTML on a tick."""
import re

from sdv.ui import data

STATIC = data.ROOT / "src/sdv/ui/static"
APP = (STATIC / "js/app.js").read_text()
UTIL = (STATIC / "js/util.js").read_text()
PAGE = (STATIC / "index.html").read_text()


def test_app_js_never_assigns_innerhtml_on_a_tick():
    assert not re.search(r"\.innerHTML\s*=", APP), "render through paint()/paintEach(); see the module docstring"


def test_the_sim_bar_groups_and_the_chips_are_painted_only_when_their_markup_changes():
    for region in ("sim-speed", "sim-jump", "sim-file"):
        assert f"paint($('{region}')" in APP, region
    assert "paintEach($('chips')" in APP and "paint($('chips')" in APP
    assert "import { esc, chip, getJSON, paint, paintEach }" in APP


def test_the_paint_helpers_compare_before_they_touch_the_dom():
    paint = re.search(r"export function paint\(el, html\) \{(.*?)\n\}", UTIL, re.S).group(1)
    assert "el.__last !== html" in paint and "el.innerHTML = html" in paint
    each = re.search(r"export function paintEach\(el, parts\) \{(.*?)\n\}", UTIL, re.S).group(1)
    assert "slot.__last === html" in each and "replaceWith" in each
    assert "el.__last = undefined" in each  # a later whole-element paint() must not skip its first repaint


def test_the_pressed_state_of_pace_and_priority_follows_the_frame():
    speed, file = re.search(r"paint\(\$\('sim-speed'\)(.*?)\);", APP, re.S).group(1), re.search(r"paint\(\$\('sim-file'\)(.*?)\);", APP, re.S).group(1)
    assert "class=\"${s === t.speed ? 'on' : ''}\" aria-pressed=\"${s === t.speed}\"" in speed
    assert "class=\"${m.id === t.mission ? 'on' : ''}\" aria-pressed=\"${m.id === t.mission}\"" in file


def test_hold_restart_and_the_view_tabs_are_static_markup():
    for control in ('id="sim-run"', 'id="sim-restart"', 'id="sim-speed"', 'id="sim-jump"', 'id="sim-file"'):
        assert control in PAGE, control
    assert len(re.findall(r'<a href="#\w+" data-view="\w+">', PAGE)) == 6
    # app.js only toggles classes and text on them (no markup assignment anywhere in the file, see above)
    assert "$('sim-run').textContent" in APP and "classList.toggle('on', a.dataset.view === app.view)" in APP
