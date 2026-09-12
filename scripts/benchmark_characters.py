"""Real, repeatable hold-out character trials. Private model assets stay in data/."""

import json, sys, time, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.closed_loop import run, write

BASE = Path(r"E:\Modelos\Animal Crossing\ACNH_2.0.0\Characters")


def main(names):
    reports = []
    for name in names:
        source = BASE / name / f"{name}.blend"
        out = ROOT / "data/character-bench" / name
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        start = time.perf_counter()
        try:
            result = run(
                source,
                out,
                "qwen3.8:27b-q4_K_M",
                lambda **kw: print(
                    json.dumps({"character": name, **kw}, ensure_ascii=True), flush=True
                ),
                corrections=1,
                separate=["mTops"],
            )
            report = {
                "character": name,
                "seconds": round(time.perf_counter() - start, 2),
                "aiAcceptable": result["aiAcceptable"],
                "review": result["iterations"][-1]["review"],
                "final": result["final"],
            }
        except Exception as e:
            report = {"character": name, "error": str(e)}
        report["source_unchanged"] = before == hashlib.sha256(source.read_bytes()).hexdigest()
        reports.append(report)
        write(ROOT / "data/character-bench/report.json", reports)
        print("CASE_RESULT", json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["Yuka", "Wolfgang"])
