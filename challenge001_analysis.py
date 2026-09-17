#!/usr/bin/env python3
"""First-pass, definition-free CAN exploration for Challenge 001.

Reads only input/.  Signal names are intentionally not assigned.
"""
from __future__ import annotations

import collections
import math
import re
from pathlib import Path

ROOT = Path("input/acquisition/L3-Charge-Slow-FullCycle_慢充全过程采集__20260911_133727_858__S0009")
FILES = [ROOT / "can/can_20260911133648.asc", ROOT / "can/can_20260911133648_2.asc"]
LINE = re.compile(r"^(\d+\.\d+)\s+\d+\s+([0-9a-fA-F]+)\s+Rx\s+d\s+(\d+)\s+(.*)$")

# Evidence-defined, deliberately conservative interiors (seconds from capture start).
PHASES = {
    "U0": (5, 35),       # initial, unconnected
    "D": (45, 55),       # door opened, before plug
    "C0": (110, 150),    # connected, not charging
    "CHG": (230, 370),   # established charging
    "C1": (400, 435),    # stopped, still connected
    "UNL": (446, 465),   # unlock-operation interval, still before unplug prompt
    "U1": (485, 530),    # after unplug
}


def read_frames():
    frames = []
    offset = 0.0
    last = 0.0
    for fi, path in enumerate(FILES):
        if fi:
            offset = last + 0.0001
        with path.open(errors="replace") as f:
            for line in f:
                m = LINE.match(line)
                if not m:
                    continue
                local, canid, dlc, payload = m.groups()
                data = bytes.fromhex(" ".join(payload.split()[: int(dlc)]))
                t = offset + float(local)
                frames.append((t, int(canid, 16), data))
                last = t
    return frames


def mode(values):
    if not values:
        return None, 0.0
    value, count = collections.Counter(values).most_common(1)[0]
    return value, count / len(values)


def phase_of(t):
    for name, (lo, hi) in PHASES.items():
        if lo <= t <= hi:
            return name
    return None


def fmt(v):
    return "--" if v is None else f"{v:02x}"


def main():
    frames = read_frames()
    per = collections.defaultdict(list)
    for t, cid, data in frames:
        per[cid].append((t, data))
    print(f"frames={len(frames)} ids={len(per)} span={frames[-1][0]:.6f}s")
    print("phase_frames", end="")
    for p in PHASES:
        print(f" {p}={sum(phase_of(t)==p for t,_,_ in frames)}", end="")
    print()

    candidates = []
    for cid, seq in per.items():
        maxlen = max(map(lambda x: len(x[1]), seq))
        for bi in range(maxlen):
            vals = {p: [] for p in PHASES}
            allvals = []
            changes = 0
            prev = None
            for t, data in seq:
                if bi >= len(data):
                    continue
                v = data[bi]
                allvals.append(v)
                if prev is not None and v != prev:
                    changes += 1
                prev = v
                p = phase_of(t)
                if p:
                    vals[p].append(v)
            modes = {p: mode(vs) for p, vs in vals.items()}
            if any(v[0] is None for v in modes.values()):
                continue
            stability = min(x[1] for x in modes.values())
            change_rate = changes / max(1, len(allvals)-1)
            pattern = tuple(modes[p][0] for p in PHASES)
            # Prefer stable phase values, reversibility U0~U1, and distinctions among
            # connection/charging states. Penalize rolling bytes.
            reversible = pattern[0] == pattern[-1]
            conn = pattern[2] != pattern[0] and pattern[4] == pattern[2]
            charge = pattern[3] != pattern[2] and pattern[4] != pattern[3]
            score = 2.0*stability + 1.5*reversible + 1.5*conn + 1.5*charge - 2.0*change_rate
            if len(set(pattern)) >= 2 and stability >= .80 and change_rate < .35:
                candidates.append((score, cid, bi, stability, change_rate, pattern))
    candidates.sort(reverse=True)
    print("\nTOP_BYTE_PHASE_PATTERNS")
    print("score id byte stable change_rate U0 D C0 CHG C1 UNL U1")
    for row in candidates[:120]:
        score, cid, bi, st, cr, pat = row
        print(f"{score:5.2f} {cid:03x} {bi} {st:.3f} {cr:.4f} " + " ".join(fmt(v) for v in pat))

    # Exact payload transitions for the strongest low-change candidate families.
    selected = {0x21d,0x132,0x43d,0x2ec,0x2e8,0x2d2,0x2a8,0x252,0x228,
                0x212,0x204,0x264,0x25d,0x333,0x24a,0x232,0x364,0x49d}
    print("\nSELECTED_PAYLOAD_TRANSITIONS (30..510s)")
    for cid in sorted(selected):
        seq = per[cid]
        runs=[]; prev=None
        for t,d in seq:
            if d != prev and 30 <= t <= 510:
                runs.append((t,d.hex()))
            prev=d
        print(f"ID {cid:03x} n={len(seq)} changes={len(runs)}")
        # Preserve event-near and long-lived changes; compact if noisy.
        if len(runs) <= 80:
            print(" ".join(f"{t:.4f}:{d}" for t,d in runs))
        else:
            near=[x for x in runs if any(abs(x[0]-a)<8 for a in (40,60,100,173,383,440,470))]
            print(" ".join(f"{t:.4f}:{d}" for t,d in near[:120]))

    # Aggregate bus activity and new/disappearing IDs in 1-second bins around anchors.
    anchors = [40,60,99.768,160,173,240,320,380,383,440,470]
    print("\nANCHOR_ACTIVITY (frames in +/-1s, changed payloads)")
    for a in anchors:
        local = [(t,c,d) for t,c,d in frames if a-1 <= t < a+1]
        changed = collections.Counter()
        prevs = {}
        for t,c,d in local:
            if c in prevs and d != prevs[c]: changed[c]+=1
            prevs[c]=d
        tops = " ".join(f"{c:03x}:{n}" for c,n in changed.most_common(8))
        print(f"{a:8.3f} frames={len(local):5d} ids={len(set(c for _,c,_ in local)):3d} {tops}")


if __name__ == "__main__":
    main()
