"""Literal content patches, evaluated against one unchanged source snapshot."""
import difflib

from backend.exceptions import NodePatchConflictError


def validate_patch(expected_version, replacements, dry_run):
    if type(expected_version) is not int or expected_version < 1:
        raise ValueError("expected_version must be a positive integer.")
    if type(dry_run) is not bool:
        raise ValueError("dry_run must be a boolean.")
    if not isinstance(replacements, list) or not replacements:
        raise ValueError("replacements must be a non-empty list.")
    for index, item in enumerate(replacements):
        if not isinstance(item, dict) or set(item) != {"old_text", "new_text", "expected_matches"}:
            raise ValueError(f"Replacement {index} requires old_text, new_text and expected_matches only.")
        if not isinstance(item["old_text"], str) or not item["old_text"]:
            raise ValueError(f"Replacement {index}: old_text must be a non-empty string.")
        if not isinstance(item["new_text"], str):
            raise ValueError(f"Replacement {index}: new_text must be a string.")
        if type(item["expected_matches"]) is not int or item["expected_matches"] < 1:
            raise ValueError(f"Replacement {index}: expected_matches must be a positive integer.")


def apply_replacements(content, replacements):
    """Count non-overlapping literal occurrences per item; reject cross-item overlap.

    New text is never searched again, so the order cannot cause cascading edits.
    """
    edits = []
    matches = []
    for index, item in enumerate(replacements):
        old_text = item["old_text"]
        start = 0
        count = 0
        while (start := content.find(old_text, start)) != -1:
            end = start + len(old_text)
            edits.append((start, end, item["new_text"]))
            count += 1
            start = end
        matches.append({"index": index, "expected_matches": item["expected_matches"], "actual_matches": count})

    if any(item["expected_matches"] != item["actual_matches"] for item in matches):
        raise NodePatchConflictError("Unexpected replacement match count.", {"matches": matches})
    edits.sort(key=lambda edit: (edit[0], edit[1]))
    if any(left[1] > right[0] for left, right in zip(edits, edits[1:])):
        raise NodePatchConflictError("Replacement matches overlap.", {"matches": matches})

    parts = []
    cursor = 0
    for start, end, new_text in edits:
        parts.extend((content[cursor:start], new_text))
        cursor = end
    parts.append(content[cursor:])
    return "".join(parts), matches


def content_diff(before, after):
    # Keep CRLF and missing final newlines visible in a unified text diff.
    lines = difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                fromfile="content:before", tofile="content:after")
    return "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
                   for line in lines)
