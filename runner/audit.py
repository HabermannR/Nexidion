"""
backend/runner/audit.py
=======================
Audit log — one instance per task execution.
Records every turn, tool call, and write operation, then serialises to JSON.
"""

import json
import os
from datetime import datetime, timezone

from runner.helpers import _iso


class Audit:
    def __init__(self, task_id, vault_id, instruction, context_node_ids, created_at):
        self.task_id          = task_id
        self.vault_id         = vault_id
        self.instruction      = instruction
        self.context_node_ids = context_node_ids
        self.created_at       = created_at
        self.started_at       = datetime.now(timezone.utc)
        self.turns: list      = []
        self.writes: list     = []
        self._current_turn: dict | None = None

    def begin_turn(self, turn_num: int):
        self._current_turn = {
            "turn":       turn_num,
            "timestamp":  _iso(),
            "elapsed_s":  None,
            "tool_calls": [],
        }

    def end_turn(self, elapsed: float):
        if self._current_turn:
            self._current_turn["elapsed_s"] = round(elapsed, 2)
            self.turns.append(self._current_turn)
            self._current_turn = None

    def record_tool(self, name: str, args: dict, result: str, detail: str):
        entry = {"name": name, "args": args, "result": result, "detail": detail}
        if self._current_turn is not None:
            self._current_turn["tool_calls"].append(entry)

    def record_write(self, operation: str, node_id: str, detail: dict):
        self.writes.append({
            "timestamp": _iso(),
            "operation": operation,
            "node_id":   node_id,
            "detail":    detail,
        })

    def save(self, outcome: str, finish_summary: str | None,
             audit_dir: str, gpt_model: str, log_fn) -> str:
        ended_at = datetime.now(timezone.utc)

        doc = {
            "task": {
                "id":               str(self.task_id),
                "vault_id":         self.vault_id,
                "instruction":      self.instruction,
                "context_node_ids": self.context_node_ids,
                "created_at":       self.created_at.isoformat(),
            },
            "started_at":     self.started_at.isoformat(),
            "ended_at":       ended_at.isoformat(),
            "duration_s":     round((ended_at - self.started_at).total_seconds(), 2),
            "outcome":        outcome,
            "finish_summary": finish_summary,
            "model":          gpt_model,
            "turns":          self.turns,
            "writes":         self.writes,
        }

        date_dir = os.path.join(audit_dir, self.started_at.strftime("%Y-%m-%d"))
        os.makedirs(date_dir, exist_ok=True)
        ts   = self.started_at.strftime("%H%M%S")
        tid  = str(self.task_id)[:8]
        path = os.path.join(date_dir, f"{tid}_{ts}.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

        log_fn(f"Audit saved → {path}")
        return path
