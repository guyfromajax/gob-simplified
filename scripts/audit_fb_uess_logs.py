#!/usr/bin/env python3
"""Summarize Fast Break UESS coverage from backend logs.

Usage:
    python scripts/audit_fb_uess_logs.py path/to/backend-log.txt

The script is read-only. It parses the shared log markers emitted by the FB
StepState hardening work:

    [FB_UESS] ...
    [FB_EMITTER_FALLBACK] ...
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Tuple


FB_UESS_RE = re.compile(
    r"\[FB_UESS\]\s+"
    r"game_id=(?P<game_id>\S+)\s+"
    r"play=(?P<play>\S+)\s+"
    r"result=(?P<result>\S+)\s+"
    r"steps=(?P<steps>\S+)\s+"
    r"schema_burn=(?P<schema_burn>\S+)\s+"
    r"time_elapsed=(?P<time_elapsed>\S+).*?"
    r"fallback=(?P<fallback>\S+)"
)
FB_FALLBACK_RE = re.compile(
    r"\[FB_EMITTER_FALLBACK\]\s+"
    r"family=(?P<family>\S+)\s+"
    r"guard=(?P<guard>\S+)\s+"
    r"detail=(?P<detail>.*?)\s+"
    r"result_type=(?P<result_type>\S+)\s+"
    r"play=(?P<play>\S+)"
)


def parse_lines(lines: Iterable[str]) -> Tuple[list[Dict[str, str]], list[Dict[str, str]]]:
    summaries = []
    fallbacks = []
    for line in lines:
        summary_match = FB_UESS_RE.search(line)
        if summary_match:
            summaries.append(summary_match.groupdict())
        fallback_match = FB_FALLBACK_RE.search(line)
        if fallback_match:
            fallbacks.append(fallback_match.groupdict())
    return summaries, fallbacks


def print_report(summaries: list[Dict[str, str]], fallbacks: list[Dict[str, str]]) -> None:
    print("Fast Break UESS Log Audit")
    print("=========================")
    print(f"FB_UESS summaries: {len(summaries)}")
    print(f"FB_EMITTER_FALLBACK hits: {len(fallbacks)}")
    print()

    if summaries:
        by_play = Counter(row["play"] for row in summaries)
        by_play_result = Counter((row["play"], row["result"]) for row in summaries)
        by_fallback = Counter(row["fallback"] for row in summaries)
        print("By play:")
        for play, count in sorted(by_play.items()):
            print(f"  {play}: {count}")
        print()
        print("By play/result:")
        for (play, result), count in sorted(by_play_result.items()):
            print(f"  {play} / {result}: {count}")
        print()
        print("Fallback values in FB_UESS summaries:")
        for fallback, count in sorted(by_fallback.items()):
            print(f"  {fallback}: {count}")
        print()

    if fallbacks:
        by_family_guard = Counter((row["family"], row["guard"]) for row in fallbacks)
        print("Emitter fallback guards:")
        for (family, guard), count in sorted(by_family_guard.items()):
            print(f"  {family}:{guard}: {count}")
        print()
        print("Fallback detail samples:")
        for row in fallbacks[:10]:
            print(
                "  "
                f"family={row['family']} guard={row['guard']} "
                f"result_type={row['result_type']} play={row['play']} "
                f"detail={row['detail']}"
            )
        print()

    covered = defaultdict(set)
    for row in summaries:
        covered[row["play"]].add(row["result"])
    print("Coverage checklist observed in this log:")
    expected = {
        "rim_runner": {"MAKE", "MISS", "BLOCK", "FOUL", "DEAD", "STEAL", "DEFENSIVE_STOP"},
        "triangle": {"MAKE", "MISS", "BLOCK", "FOUL", "DEAD", "STEAL", "DEFENSIVE_STOP"},
        "covert_release": {"MAKE", "MISS", "BLOCK", "FOUL", "DEAD", "STEAL", "DEFENSIVE_STOP"},
        "after_steal": {"MAKE", "MISS", "BLOCK", "FOUL", "DEAD"},
    }
    for play, expected_results in expected.items():
        observed = covered.get(play, set())
        missing = sorted(expected_results - observed)
        print(
            f"  {play}: observed={sorted(observed) or 'none'} "
            f"missing={missing or 'none'}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", type=Path)
    args = parser.parse_args()

    with args.log_file.open("r", encoding="utf-8", errors="replace") as handle:
        summaries, fallbacks = parse_lines(handle)
    print_report(summaries, fallbacks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
