"""`sdv`: the one documented command.

    sdv sim scenario-b [--seed 1] [--mission survey] [--until-min 25] [--speed 12] [--out runs/b.jsonl]
    sdv replay-check scenario-b [--seed 1] [--until-min 25]      # two runs, hashes must match
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .data import load_inputs
from .plant.sim import Simulator, write_jsonl


def _fmt_tick(s: dict) -> str:
    g = s["gauges"]
    ship = s["ship"]
    guests = " ".join(f"{k}:{v['mode']}@{v['actual_kw']:g}kW" for k, v in s["guests"].items())
    ev = ("  <- " + ", ".join(e["type"] for e in s["events"])) if s["events"] else ""
    return (f"{s['t_min']:6.2f} min | {ship['speed_band']:7} {ship['course']:6} {ship['noise']:7} deck={ship['deck']:8} "
            f"em={ship['emission']:6} gen={ship['genset']} cool={ship['cooling']:8} | "
            f"P {g['power']['committed']:6.1f}/{g['power']['capacity']:5.0f}  H {g['heat']['committed']:6.1f}/{g['heat']['capacity']:5.1f} "
            f"mass {g['mass']['committed']:5.2f}/{g['mass']['capacity']:g} | {guests}{ev}")


def cmd_sim(args: argparse.Namespace) -> int:
    inputs = load_inputs(args.scenario)
    sim = Simulator(inputs, seed=args.seed, mission=args.mission)
    every = int(args.print_every * 60)

    def sink(s: dict) -> None:
        if args.quiet:
            return
        if s["events"] or (every and s["t_s"] % every == 0):
            print(_fmt_tick(s))

    h = sim.run(args.until_min, realtime_factor=args.speed, sink=sink)
    out = Path(args.out) if args.out else Path("runs") / f"{inputs.scenario['id']}_{args.mission or 'nomission'}_s{args.seed}.jsonl"
    write_jsonl(out, sim)
    print(f"run_hash {h}  ticks {len(sim.snapshots)}  -> {out}")
    return 0


def cmd_replay_check(args: argparse.Namespace) -> int:
    hashes = []
    for _ in range(2):
        sim = Simulator(load_inputs(args.scenario), seed=args.seed, mission=args.mission)
        hashes.append(sim.run(args.until_min))
    ok = hashes[0] == hashes[1]
    print(f"run 1 {hashes[0]}\nrun 2 {hashes[1]}\n{'IDENTICAL' if ok else 'DIFFERENT'}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdv", description="ArgOS resource governor for a software-defined vessel")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("scenario", help="scenario id (scenario-b) or path to a YAML file")
        sp.add_argument("--seed", type=int, default=1)
        sp.add_argument("--mission", help="priority file id (survey, sar, patrol, disaster_relief)")
        sp.add_argument("--until-min", type=float, default=25.0)

    s = sub.add_parser("sim", help="run the plant open loop and write a JSONL run")
    common(s)
    s.add_argument("--speed", type=float, default=0.0, help="ship-seconds per wall-second; 0 = flat out, 12 = demo pace")
    s.add_argument("--print-every", type=float, default=1.0, help="print a line every N ship-minutes (0 = events only)")
    s.add_argument("--quiet", action="store_true")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_sim)

    r = sub.add_parser("replay-check", help="run twice, compare run hashes")
    common(r)
    r.set_defaults(fn=cmd_replay_check)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
