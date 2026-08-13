"""Inspect an agent Responses stream trace without needing Docker logs."""

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path


def _trace_path(task_id, trace_dir):
    return Path(trace_dir) / f"{task_id}.jsonl"


def _print_record(record, show_payload):
    line = f"turn {record.get('turn')}  +{record.get('elapsed_s', 0):>8}s  {record.get('event')}"
    print(line, flush=True)
    if show_payload and "payload" in record:
        print(json.dumps(record["payload"], ensure_ascii=False, indent=2), flush=True)


def inspect_trace(task_id, trace_dir, follow=False, show_payload=False):
    path = _trace_path(task_id, trace_dir)
    while not path.exists():
        if not follow:
            raise SystemExit(f"No stream trace found at {path}")
        time.sleep(0.5)

    counts = Counter()
    with path.open(encoding="utf-8") as trace:
        while True:
            line = trace.readline()
            if line:
                record = json.loads(line)
                counts[record.get("event", "unknown")] += 1
                _print_record(record, show_payload)
                continue
            if not follow:
                break
            time.sleep(0.5)
    if not follow:
        print("\nEvent totals:")
        for event, count in counts.most_common():
            print(f"  {count:>6}  {event}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    parser.add_argument("--follow", action="store_true")
    parser.add_argument(
        "--payloads", action="store_true",
        help="show captured payloads (only available when capture was enabled; may contain note text)",
    )
    parser.add_argument(
        "--trace-dir", default=os.environ.get("NEXIDION_STREAM_DEBUG_DIR", "./audit_logs/streams"),
    )
    args = parser.parse_args()
    inspect_trace(args.task_id, args.trace_dir, args.follow, args.payloads)


if __name__ == "__main__":
    main()
