# -*- coding: utf-8 -*-
"""Route performance benchmark. Run via FreeCADCmd.exe benchmarks/route_perf.py
--pass --record saves benchmarks/baseline.json; --pass --runs N compares timing + fingerprint.
Exit code 1 on fingerprint mismatch or missing baseline."""

import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

BASE = os.path.dirname(os.path.abspath(__file__))
DOC_PATH = os.path.join(BASE, "..", "Examples", "Example.FCStd")
BASELINE_PATH = os.path.join(BASE, "baseline.json")


def round_point(p):
    return (round(p.x, 6), round(p.y, 6), round(p.z, 6))


def fingerprint(route):
    h = hashlib.sha256()

    def feed(obj):
        if isinstance(obj, FreeCAD.Vector):
            h.update(repr(round_point(obj)).encode())
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                feed(item)
        else:
            value = round(float(obj), 6) if isinstance(obj, float) else obj
            h.update(repr(value).encode())

    feed(route.Offset_L)
    feed(route.Offset_R)
    feed(route.RouteBreaks)
    feed(route.Pauses)
    feed(route.PausesDurations)
    feed(route.FeedOverrides)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--label", default="NACA0012_Left")
    args = parser.parse_args()

    doc = App.openDocument(DOC_PATH)
    route = doc.getObjectsByLabel(args.label)[0]

    # throwaway run to settle initialization, then measured runs
    route.touch()
    route.recompute()

    times = []
    fp = None
    for _ in range(args.runs):
        route.touch()
        t0 = time.perf_counter()
        route.recompute()
        times.append(time.perf_counter() - t0)
        fp = fingerprint(route)

    times.sort()
    median = times[len(times) // 2]

    print("route: {}".format(route.Label))
    print("runs: {}".format([round(t, 4) for t in times]))
    print("median: {:.4f} s".format(median))
    print("fingerprint: {}".format(fp))

    if args.record:
        data = {"label": route.Label, "median_s": median, "times_s": times, "fingerprint": fp}
        with open(BASELINE_PATH, "w") as f:
            json.dump(data, f, indent=2)
        print("baseline saved to {}".format(BASELINE_PATH))
        return 0

    if not os.path.exists(BASELINE_PATH):
        print("No baseline found. Run with --record first.")
        return 1

    with open(BASELINE_PATH) as f:
        baseline = json.load(f)

    ok = True
    if fp != baseline["fingerprint"]:
        print("FINGERPRINT MISMATCH: got {}, baseline {}".format(fp, baseline["fingerprint"]))
        ok = False
    else:
        print("fingerprint matches baseline")
    print("baseline median: {:.4f} s (speedup {:.2f}x)".format(baseline["median_s"], baseline["median_s"] / median))
    return 0 if ok else 1


# FreeCADCmd imports the passed script as a module (never __main__) and
# rejects our flags, so run when this file is the entry script, reconstruct
# sys.argv (strip --pass and the script path), and flush before exit.
if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    script_args = [a for a in sys.argv[1:] if a != "--pass" and os.path.abspath(a) != os.path.abspath(__file__)]
    sys.argv = [sys.argv[0]] + script_args
    code = main()
    sys.stdout.flush()
    sys.exit(code)
