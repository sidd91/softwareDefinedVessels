"""Build the deliverable PDFs and check their page limits (brief: README <= 3 pages, Scenario C memo
<= 2 pages, Physical Account 1 page).

Preferred route: pandoc turns the Markdown into one self-contained HTML file styled by tools/pdf/print.css,
headless Chromium prints it on US Letter and on A4 (the jury's paper size is not stated), and pdfinfo
counts the pages. The Physical Account prints landscape. Fallback route, used when pandoc or Chromium is
missing or when asked for: LibreOffice converts the Markdown directly, portrait, on its default paper
(US Letter on this laptop) with its own larger styles, so a document that fits there also fits on the
preferred route. Mermaid diagrams cannot render offline, so on both routes each one is drawn as an SVG
image by the small layered layout below, never printed as source.

Run (a freeze-time check, not part of the default pytest run):
    uv run python tools/build_pdfs.py                  # build all into docs/pdf/ and check limits
    uv run python tools/build_pdfs.py memo             # one document: readme, memo or account
    uv run python tools/build_pdfs.py --libreoffice    # force the fallback route
Exit code 1 if any document is over its limit. docs/pdf/ keeps the Letter print.
"""
from html import escape
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "tools/pdf/print.css"
OUT = ROOT / "docs/pdf"
DOCS = {  # key: (source, output name, page limit, landscape)
    "readme": ("README.md", "README.pdf", 3, False),
    "memo": ("docs/SCENARIO_C_MEMO.md", "SCENARIO_C_MEMO.pdf", 2, False),
    "account": ("docs/PHYSICAL_ACCOUNT.md", "PHYSICAL_ACCOUNT.pdf", 1, True),
}
SIZES = ("Letter", "A4")


def run(cmd: list[str], **kw) -> None:
    """Run a converter; on failure stop with the tool's own error text."""
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)
    except subprocess.CalledProcessError as e:
        sys.exit(f"{Path(cmd[0]).name} failed: {(e.stderr or e.stdout or '').strip()[-800:]}")


def chromium():
    for name in ("chromium", "chromium-browser", "google-chrome"):
        path = shutil.which(name) or (f"/snap/bin/{name}" if Path(f"/snap/bin/{name}").exists() else None)
        if path:
            return path
    return None


def pages(pdf: Path) -> tuple[int, str]:
    """Page count and paper name (Letter, A4 or the size in points) from pdfinfo."""
    info = subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True).stdout
    w, h = (round(float(v)) for v in re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info).groups())
    paper = {(612, 792): "Letter", (595, 842): "A4"}.get((min(w, h), max(w, h)), f"{w}x{h} pt")
    return int(re.search(r"Pages:\s+(\d+)", info).group(1)), paper + (" landscape" if w > h else "")


# ---- Mermaid flowchart to SVG (subset: flowchart/graph LR|TD, subgraph ... end, A[label], A --> B,
# A & B --> C, chains, edge labels -->|x|). Layered layout: longest-path ranks, sources pulled next to
# their nearest target, dummy points for long edges, two down-and-up barycentre sweeps.

ARROW = re.compile(r"\s*(-->\|([^|]*)\||--\s+([^->][^>]*?)\s*-->|-\.->|-->|---|==>)\s*")
FONT, CHAR, WRAP, PAD, GAP_RANK, GAP_NODE = 12, 6.4, 24, 8, 30, 12


def _split_outside(text: str, pattern: re.Pattern) -> list[str]:
    """Split on pattern only outside brackets, keeping captured edge labels at odd positions."""
    out, depth, start, i = [], 0, 0, 0
    while i < len(text):
        c = text[i]
        if c in "[({":
            depth += 1
        elif c in "])}":
            depth -= 1
        m = pattern.match(text, i) if depth == 0 and c in "-=" else None
        if m and m.end() > i:
            out += [text[start:i], (m.group(2) or m.group(3) or "").strip()]
            start = i = m.end()
            continue
        i += 1
    return out + [text[start:]]


def _ref(token: str) -> tuple[str, str | None]:
    m = re.match(r"\s*([A-Za-z_][\w-]*)\s*(?:[\[({]+(.*?)[\])}]+)?\s*$", token)
    if not m:
        return token.strip(), None
    label = m.group(2)
    return m.group(1), label.strip().strip('"') if label is not None else None


def mermaid_svg(src: str) -> str:
    direction, labels, order, groups, stack, edges = "LR", {}, [], [], [], []

    def define(token):
        nid, label = _ref(token)
        if nid not in labels:
            labels[nid] = nid
            order.append(nid)
        if label is not None:
            labels[nid] = label
        if stack and not any(nid in g[2] for g in groups):
            stack[-1][2].append(nid)
        return nid

    for raw in src.splitlines():
        line = raw.split("%%")[0].strip().rstrip(";")
        if not line or re.match(r"(direction|classDef|class|style|linkStyle|click)\b", line):
            continue
        if m := re.match(r"(?:flowchart|graph)\s+(\w+)", line):
            direction = "TD" if m.group(1).upper() in ("TD", "TB") else "LR"
        elif m := re.match(r"subgraph\s+(.+)", line):
            gid, label = _ref(m.group(1))
            groups.append((gid, label or m.group(1).strip().strip('"'), []))
            stack.append(groups[-1])
        elif line == "end":
            stack and stack.pop()
        else:
            parts, prev = _split_outside(line, ARROW), None
            for i in range(0, len(parts), 2):
                ids = [define(t) for t in re.split(r"\s+&\s+", parts[i]) if t.strip()]
                if prev:
                    edges += [(a, b, parts[i - 1]) for a in prev for b in ids]
                prev = ids

    if not order:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="1in" height="0.1in"/>'
    # Node sizes (along the rank axis, across it), with labels wrapped like mermaid does.
    lines = {n: [w for part in re.split(r"<br\s*/?>", labels[n]) for w in textwrap.wrap(part, WRAP) or [""]]
             for n in order}
    size = {n: (max(len(s) for s in lines[n]) * CHAR + 2 * PAD, len(lines[n]) * (FONT + 3) + 2 * PAD - 3)
            for n in order}
    along = {n: size[n][0] if direction == "LR" else size[n][1] for n in order}
    across = {n: size[n][1] if direction == "LR" else size[n][0] for n in order}

    succ = {n: [b for a, b, _ in edges if a == n and b != n] for n in order}
    pred = {n: [a for a, b, _ in edges if b == n and a != n] for n in order}
    rank, todo = {}, list(order)
    for _ in range(len(order) + 1):  # longest path; a cycle falls back to rank 0
        for n in list(todo):
            if all(p in rank for p in pred[n]):
                rank[n] = max((rank[p] + 1 for p in pred[n]), default=0)
                todo.remove(n)
    rank.update({n: 0 for n in todo})
    # Pull each source next to its nearest target; sources in one subgraph move together.
    want = {n: max(0, min(rank[s] for s in succ[n]) - 1) for n in order if not pred[n] and succ[n]}
    for _gid, _label, members in groups:
        moving = [n for n in members if n in want]
        for n in moving:
            want[n] = min(want[m] for m in moving)
    rank.update(want)

    # Chains of points per edge, with dummy points on the ranks a long edge crosses.
    layer = {r: [n for n in order if rank[n] == r] for r in range(max(rank.values(), default=0) + 1)}
    chains = []
    for k, (a, b, label) in enumerate(edges):
        chain = [a]
        for r in range(rank[a] + 1, rank[b]):
            d = f"_d{k}_{r}"
            along[d] = across[d] = 0
            layer[r].append(d)
            chain.append(d)
        chains.append((chain + [b], label))
    nbr_in = {n: [] for r in layer for n in layer[r]}
    nbr_out = {n: [] for r in layer for n in layer[r]}
    for chain, _ in chains:
        for u, v in zip(chain, chain[1:]):
            nbr_out[u].append(v)
            nbr_in[v].append(u)
    group_of = {n: i for i, g in enumerate(groups) for n in g[2]}
    for sweep in range(4):  # barycentre ordering, members of one group kept together
        ranks = sorted(layer) if sweep % 2 == 0 else sorted(layer, reverse=True)
        for r in ranks:
            nbrs = nbr_in if sweep % 2 == 0 else nbr_out
            ref = layer.get(r - 1 if sweep % 2 == 0 else r + 1, [])
            pos = {n: i for i, n in enumerate(ref)}
            bary = {n: (sum(pos[m] for m in nbrs[n] if m in pos) / max(1, sum(m in pos for m in nbrs[n]))
                        if any(m in pos for m in nbrs[n]) else i) for i, n in enumerate(layer[r])}
            gkey = {}
            for n in layer[r]:
                gkey.setdefault(group_of.get(n, n), []).append(bary[n])
            layer[r].sort(key=lambda n: (sum(gkey[group_of.get(n, n)]) / len(gkey[group_of.get(n, n)]), bary[n]))

    # Coordinates: u along the rank axis, v across it; each layer centred on the tallest one.
    width = {r: max((along[n] for n in layer[r]), default=0) for r in layer}
    u0, u = {}, 0
    for r in sorted(layer):
        u0[r], u = u, u + width[r] + GAP_RANK * (2 if direction == "LR" else 1.5)
    span = {r: sum(across[n] or 4 for n in layer[r]) + GAP_NODE * (len(layer[r]) - 1) for r in layer}
    tall = max(span.values(), default=0)
    U, V = {}, {}
    for r in layer:
        v = (tall - span[r]) / 2
        for n in layer[r]:
            U[n], V[n] = u0[r] + (width[r] - along[n]) / 2, v
            v += (across[n] or 4) + GAP_NODE

    def xy(n, end):  # anchor where an edge leaves (end=1) or enters (end=0) a node
        uu, vv = U[n] + along[n] * end, V[n] + (across[n] or 4) / 2
        return (uu, vv) if direction == "LR" else (vv, uu)

    def box(n):
        return (U[n], V[n], along[n], across[n]) if direction == "LR" else (V[n], U[n], across[n], along[n])

    parts, xs, ys = [], [], []
    for gid, glabel, members in groups:
        if not members:
            continue
        bx = [box(n) for n in members]
        x0, y0 = min(b[0] for b in bx) - 10, min(b[1] for b in bx) - 10 - FONT - 4
        x1, y1 = max(b[0] + b[2] for b in bx) + 10, max(b[1] + b[3] for b in bx) + 10
        x1 = max(x1, x0 + len(glabel) * CHAR + 2 * PAD)
        xs += [x0, x1]
        ys += [y0, y1]
        parts.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="6" '
                     f'fill="#f3f4f6" stroke="#9ca3af"/><text x="{x0 + 8:.1f}" y="{y0 + FONT + 2:.1f}" '
                     f'font-weight="bold">{escape(glabel)}</text>')
    for chain, label in chains:
        pts = [xy(chain[0], 1)] + [xy(n, 0) for n in chain[1:-1]] + [xy(chain[-1], 0)]
        d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if direction == "LR":
                xm = (x0 + x1) / 2
                d += f" C{xm:.1f},{y0:.1f} {xm:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
            else:
                ym = (y0 + y1) / 2
                d += f" C{x0:.1f},{ym:.1f} {x1:.1f},{ym:.1f} {x1:.1f},{y1:.1f}"
        parts.append(f'<path d="{d}" fill="none" stroke="#4b5563" stroke-width="1.1" marker-end="url(#arrow)"/>')
        if label:
            (x0, y0), (x1, y1) = pts[0], pts[1]
            parts.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{(y0 + y1) / 2 - 3:.1f}" text-anchor="middle" '
                         f'font-size="{FONT - 2}">{escape(label)}</text>')
    for n in order:
        x, y, w, h = box(n)
        xs += [x, x + w]
        ys += [y, y + h]
        text = "".join(f'<tspan x="{x + w / 2:.1f}" dy="{FONT + 3 if i else 0}">{escape(s)}</tspan>'
                       for i, s in enumerate(lines[n]))
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="4" fill="#ffffff" '
                     f'stroke="#374151"/><text x="{x + w / 2:.1f}" y="{y + PAD + FONT - 2:.1f}" '
                     f'text-anchor="middle">{text}</text>')
    x0, y0, W, H = min(xs) - 4, min(ys) - 4, max(xs) - min(xs) + 8, max(ys) - min(ys) + 8
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.1f} {y0:.1f} {W:.1f} {H:.1f}" '
            f'width="{6.5:.2f}in" height="{6.5 * H / W:.2f}in" font-family="Liberation Sans, Arial, sans-serif" '
            f'font-size="{FONT}" fill="#111111"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#4b5563"/>'
            f'</marker></defs>{"".join(parts)}</svg>')


def prepare(md: str, tmp: Path, key: str, html: bool) -> str:
    """Swap each mermaid block for an SVG drawing of it, written next to the Markdown."""
    count = 0

    def draw(m):
        nonlocal count
        count += 1
        svg = tmp / f"{key}-diagram-{count}.svg"
        svg.write_text(mermaid_svg(m.group(1)))
        if html:
            return f'<p class="diagram"><img src="{svg.name}" alt="Architecture diagram"></p>'
        return f"![Architecture diagram]({svg.name})"

    return re.sub(r"```mermaid\n(.*?)```", draw, md, flags=re.S)


def libreoffice(key: str, tmp: Path) -> tuple[Path, int, str]:
    src, _name, _limit, _landscape = DOCS[key]
    md = tmp / f"{key}.md"
    md.write_text(prepare((ROOT / src).read_text(), tmp, key, html=False))
    run(["soffice", f"-env:UserInstallation={(tmp / ('lo-' + key)).as_uri()}", "--headless",
         "--convert-to", "pdf", "--outdir", str(tmp), str(md)], timeout=180)
    pdf = tmp / f"{key}.pdf"
    return (pdf, *pages(pdf))


def build(key: str, size: str, tmp: Path) -> tuple[Path, int, str]:
    src, name, _limit, landscape = DOCS[key]
    md = tmp / f"{key}.md"
    md.write_text(prepare((ROOT / src).read_text(), tmp, key, html=True))
    css = tmp / f"print-{key}-{size}.css"
    css.write_text(CSS.read_text().replace("var(--page, Letter)", f"{size} landscape" if landscape else size)
                   + ("\ntable { font-size: 8.3pt; }\n" if landscape else ""))   # the one-page account's dense table
    html = tmp / f"{key}-{size}.html"
    run(["pandoc", str(md), "-f", "gfm", "-t", "html5", "--standalone", "--embed-resources",
         f"--resource-path={tmp}:{(ROOT / src).parent}", "--metadata", f"pagetitle={name[:-4]}",
         "--css", css.name, "-o", str(html)], cwd=tmp, timeout=120)
    pdf = tmp / f"{key}-{size}.pdf"
    run([chromium(), "--headless", "--disable-gpu", "--no-sandbox", f"--user-data-dir={tmp / 'chrome'}",
         "--no-pdf-header-footer", f"--print-to-pdf={pdf}", html.as_uri()], timeout=180)
    return (pdf, *pages(pdf))


def main(args):
    force_lo = "--libreoffice" in args
    keys = [a for a in args if not a.startswith("--")] or list(DOCS)
    unknown = [k for k in keys if k not in DOCS]
    if unknown:
        sys.exit(f"unknown document {unknown}; choose from {', '.join(DOCS)}")
    OUT.mkdir(parents=True, exist_ok=True)
    fast = not force_lo and shutil.which("pandoc") and chromium()
    if not fast and not shutil.which("soffice"):
        sys.exit("no PDF route: install pandoc and Chromium (preferred) or LibreOffice (fallback)")
    print("route: pandoc + headless Chromium (Letter and A4)" if fast else
          "route: LibreOffice fallback (" + ("forced" if force_lo else "pandoc or Chromium missing")
          + "; default paper, portrait, larger styles)")
    # Snap Chromium may only read files under ~/snap/chromium, so work there when it exists.
    snap = Path.home() / "snap/chromium/common"
    over = False
    with tempfile.TemporaryDirectory(prefix="sdv-pdf-", dir=snap if snap.exists() else None) as t:
        tmp = Path(t)
        for key in keys:
            src, name, limit, _ = DOCS[key]
            counts = []
            for size in (SIZES if fast else [None]):
                pdf, n, paper = build(key, size, tmp) if fast else libreoffice(key, tmp)
                counts.append((paper, n))
                if size in ("Letter", None):
                    shutil.copy(pdf, OUT / name)
            ok = all(n <= limit for _, n in counts)
            over |= not ok
            print(f"{'ok  ' if ok else 'OVER'} {src}: " + ", ".join(f"{p} {n}" for p, n in counts)
                  + f" pages (limit {limit})")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
