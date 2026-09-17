#!/usr/bin/env python3
"""Round-2 definition-free exploration. Evidence source is input/ only."""
from __future__ import annotations

import collections
import re
from pathlib import Path

BASE = Path("input/acquisition/L3-Charge-Slow-FullCycle_慢充全过程采集__20260911_133727_858__S0009")
FILES = [BASE / "can/can_20260911133648.asc", BASE / "can/can_20260911133648_2.asc"]
RX = re.compile(r"^(\d+\.\d+)\s+\d+\s+([0-9a-fA-F]+)\s+Rx\s+d\s+(\d+)\s+(.*)$")

# Interior windows avoid transition periods and event-prompt ambiguity.
PHASES = {
    "U0": (5, 35),
    "DOOR": (45, 55),
    "CONN": (110, 150),
    "CHG": (230, 370),
    "STOP_CONN": (400, 435),
    "UNLOCK": (446, 465),
    "U1": (485, 530),
}
EVENTS = {"door":40.04, "plug":60.04, "charge":173.35,
          "stop":381.57, "unlock":440.06, "unplug":470.17}


def frames():
    offset = 0.0
    last = 0.0
    for fi, path in enumerate(FILES):
        if fi:
            offset = last + 0.0001
        with path.open(errors="replace") as src:
            for line in src:
                m = RX.match(line)
                if not m:
                    continue
                local, cid, dlc, tail = m.groups()
                t = offset + float(local)
                last = t
                yield t, int(cid, 16), bytes.fromhex(" ".join(tail.split()[:int(dlc)]))


def phase(t):
    for name, (lo, hi) in PHASES.items():
        if lo <= t <= hi:
            return name
    return None


def mode(counter):
    if not counter:
        return None, 0.0
    v, n = counter.most_common(1)[0]
    return v, n / sum(counter.values())


def main():
    # byte_counts[(id, byte, phase)][value]; exact payload transition stream retained
    # only when payload changes, keeping memory bounded.
    byte_counts = collections.defaultdict(collections.Counter)
    payload_counts = collections.defaultdict(collections.Counter)
    previous = {}
    changes = collections.defaultdict(list)
    message_count = collections.Counter()
    for t, cid, data in frames():
        message_count[cid] += 1
        p = phase(t)
        if p:
            payload_counts[(cid,p)][data] += 1
            for i,v in enumerate(data):
                byte_counts[(cid,i,p)][v] += 1
        old = previous.get(cid)
        if old is not None and old != data:
            changes[cid].append((t, old, data))
        previous[cid] = data

    # Exact bit candidates from per-byte modal patterns. Bits are numbered LSB=0.
    bit_rows=[]
    byte_rows=[]
    for cid in message_count:
        dlc=max((i for c,i,p in byte_counts if c==cid), default=-1)+1
        for bi in range(dlc):
            ms=[]; purity=[]
            for p in PHASES:
                v,q=mode(byte_counts[(cid,bi,p)])
                ms.append(v); purity.append(q)
            if any(v is None for v in ms): continue
            if len(set(ms))>1:
                byte_rows.append((min(purity),cid,bi,tuple(ms)))
            for bit in range(8):
                bp=[]; bq=[]
                for p in PHASES:
                    c=byte_counts[(cid,bi,p)]
                    ones=sum(n for v,n in c.items() if v&(1<<bit))
                    total=sum(c.values())
                    zeros=total-ones
                    bp.append(int(ones>zeros)); bq.append(max(ones,zeros)/total)
                pat=tuple(bp)
                if len(set(pat))>1 and min(bq)>=.995:
                    # Useful shapes: full reversible cycle, charge-only, or retained after stop.
                    reversible=pat[0]==pat[-1]
                    conn=(pat[2]!=pat[0] and pat[4]==pat[2])
                    chg=(pat[3]!=pat[2] and pat[4]!=pat[3])
                    retained=(pat[3]!=pat[2] and pat[4]==pat[3] and pat[-1]==pat[0])
                    score=2*min(bq)+2*reversible+2*conn+2*chg+retained
                    bit_rows.append((score,min(bq),cid,bi,bit,pat))
    bit_rows.sort(reverse=True)
    byte_rows.sort(reverse=True)
    print("TOP_BITS: score purity id byte bit U0 DOOR CONN CHG STOP_CONN UNLOCK U1")
    for x in bit_rows[:160]:
        score,purity,cid,bi,bit,pat=x
        print(f"{score:.2f} {purity:.4f} {cid:03x} {bi} {bit} " + " ".join(map(str,pat)))

    print("\nTOP_BYTES: purity id byte modes")
    for purity,cid,bi,pat in byte_rows[:120]:
        print(f"{purity:.4f} {cid:03x} {bi} " + " ".join(f"{v:02x}" for v in pat))

    # For selected high-value families, show XOR masks and field-local transitions near anchors.
    selected={0x21d,0x43d,0x264,0x204,0x212,0x252,0x2d2,0x24a,
              0x2ec,0x2e8,0x2a8,0x333,0x49d,0x132,0x228,0x288,
              0x232,0x20a,0x364,0x472,0x32a,0x25d}
    print("\nSELECTED_PHASE_MODES")
    for cid in sorted(selected):
        vals=[]
        for p in PHASES:
            v,q=mode(payload_counts[(cid,p)])
            vals.append("--" if v is None else f"{v.hex()}({q:.3f})")
        print(f"{cid:03x} " + " ".join(vals))

    print("\nEVENT_NEAR_TRANSITIONS")
    for cid in sorted(selected):
        xs=[]
        for t,a,b in changes[cid]:
            near=[name for name,e in EVENTS.items() if abs(t-e)<3]
            if near:
                # changed-bit mask, per byte
                mask=bytes(x^y for x,y in zip(a,b)).hex()
                xs.append(f"{t:.4f}/{near[0]}:{a.hex()}>{b.hex()} xor={mask}")
        if xs:
            print(f"ID {cid:03x}")
            print("\n".join(xs[:120]))


if __name__ == "__main__":
    main()
