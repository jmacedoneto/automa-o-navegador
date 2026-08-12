from pathlib import Path
import sys


# Make `app.*` importable when running tests from backend/.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Make `cotacao_pvs` importable as a top-level package during backend
# tests (the test file layout lives in examples/, but the legacy
# cotacao_pvs driver only sits there — we still want a top-level
# import to work the same way pytest does for examples/cotacao_pvs/tests).
EXAMPLES = ROOT / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))
