"""One instrumented scan against the real Claude API.

Runs the exact same code the app uses, prints every step with timing,
and writes everything (including full tracebacks and the suggestions) to
scan_debug.log. Run it once, paste the log — no guessing.

Usage, from the backend/ directory:

    pip install -r requirements.txt          # once
    export ANTHROPIC_API_KEY=sk-ant-...
    python diagnose_scan.py "Rhythm Future Quartet"

Cost: one scan (~$0.10-0.50). No database or web server needed.
"""

import json
import os
import sys
import time
import traceback

from app import discovery

LOG_PATH = "scan_debug.log"


def main() -> None:
    artist = sys.argv[1] if len(sys.argv) > 1 else "Rhythm Future Quartet"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first: export ANTHROPIC_API_KEY=sk-ant-...")

    log = open(LOG_PATH, "w", encoding="utf-8")
    started = time.time()

    def note(message: str) -> None:
        line = f"[{time.time() - started:7.1f}s] {message}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    note(f"model={discovery.DISCOVERY_MODEL}")
    note(f"max searches={discovery.MAX_WEB_SEARCHES}")
    note(f"scan cap={discovery.SCAN_MAX_SECONDS:.0f}s")
    note(f"scanning artist: {artist!r}")

    try:
        suggestions = discovery.run_discovery([artist], progress=note)
    except Exception:
        note("SCAN FAILED — traceback follows")
        log.write(traceback.format_exc())
        log.flush()
        traceback.print_exc()
        print(f"\nPaste the contents of {LOG_PATH} when reporting.")
        sys.exit(1)

    note(f"SCAN SUCCEEDED — {len(suggestions)} suggestions")
    for suggestion in suggestions:
        log.write(json.dumps(suggestion, ensure_ascii=False) + "\n")
        print(f"  - {suggestion['name']} ({suggestion['type']})")
    log.flush()
    print(f"\nFull detail in {LOG_PATH}.")


if __name__ == "__main__":
    main()
