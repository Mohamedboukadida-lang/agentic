"""Render an eval Report as Markdown or JSON."""

from __future__ import annotations

import json
from dataclasses import asdict

from ragent.eval.runner import Report


def to_json(report: Report) -> str:
    return json.dumps(asdict(report), indent=2, default=str)


def to_markdown(report: Report, title: str = "") -> str:
    lines = [f"## {title or report.kind.capitalize() + ' eval'}", ""]
    if report.config:
        lines += ["Config: " + ", ".join(f"`{k}={v}`" for k, v in report.config.items()), ""]
    lines += ["| Metric | Value |", "| --- | --- |"]
    lines += [f"| {name} | {value:g} |" for name, value in report.summary.items()]
    columns = sorted({key for stats in report.by_type.values() for key in stats} - {"n"})
    if report.by_type:
        lines += [
            "",
            "| Type | n | " + " | ".join(columns) + " |",
            "| --- | --- |" + " --- |" * len(columns),
        ]
        for kind, stats in report.by_type.items():
            cells = [f"{stats[c]:g}" if c in stats else "" for c in columns]
            lines.append(f"| {kind} | {stats['n']:g} | " + " | ".join(cells) + " |")
    if report.kind == "retrieval":
        misses = [r for r in report.rows if not r["hit"]]
        if misses:
            lines += ["", "Misses:", ""]
            lines += [
                f"- `{r['id']}` retrieved {', '.join(r['retrieved']) or 'nothing'}" for r in misses
            ]
    return "\n".join(lines) + "\n"
