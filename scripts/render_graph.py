#!/usr/bin/env python3
"""Render the LangGraph diagram: docs/architecture.mmd always, docs/architecture.png
when mermaid-ink is reachable (draw_mermaid_png needs network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.graph import _compiled as graph


def main() -> None:
    docs = Path(__file__).resolve().parent.parent / "docs"
    mmd = graph.get_graph().draw_mermaid()
    (docs / "architecture.mmd").write_text(mmd + "\n")
    print(f"wrote {docs / 'architecture.mmd'}")
    try:
        png = graph.get_graph().draw_mermaid_png()
        (docs / "architecture.png").write_bytes(png)
        print(f"wrote {docs / 'architecture.png'}")
    except Exception as e:  # noqa: BLE001 — offline CI: .mmd is the fallback artifact
        print(f"PNG render skipped ({e}); docs/architecture.mmd is the checked-in diagram")


if __name__ == "__main__":
    main()
