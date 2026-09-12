"""Fresh complete-figure evaluations, with no reused semantic decisions."""

import argparse, hashlib, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.closed_loop import run, write
from backend.assembly import assemble


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()
    summary = []
    if args.output.exists():
        raise SystemExit("Use a new output folder for a fresh benchmark.")
    for source in args.sources:
        out = args.output / source.stem
        start = time.perf_counter()
        before = hashlib.sha256(source.read_bytes()).hexdigest()

        def progress(**values):
            if values.get("message"):
                print(source.stem, values["message"], flush=True)

        try:
            body = run(
                source,
                out / "body",
                args.model,
                progress,
                corrections=0,
                defer_review=True,
                separate=["mTops"],
            )
            cloth = run(
                source,
                out / "clothing",
                args.model,
                progress,
                corrections=0,
                defer_review=True,
                target=["mTops"],
            )
            final = assemble(
                out / "body", out / "clothing", out / "complete", progress, automatic=True
            )
            row = {
                "character": source.stem,
                "seconds": round(time.perf_counter() - start, 2),
                "aiAcceptable": final["aiAcceptable"],
                "initialBodyReview": body["iterations"][0]["review"],
                "initialClothingReview": cloth["iterations"][0]["review"],
                "finish": final.get("finish", {}),
                "path": str((out / "complete").resolve()),
            }
        except Exception as error:
            row = {
                "character": source.stem,
                "seconds": round(time.perf_counter() - start, 2),
                "error": str(error),
            }
        row["originalUnchanged"] = before == hashlib.sha256(source.read_bytes()).hexdigest()
        summary.append(row)
        write(args.output / "report.json", summary)
        print(
            "COMPLETE",
            json.dumps(
                {
                    k: v
                    for k, v in row.items()
                    if k not in {"initialBodyReview", "initialClothingReview", "finish"}
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
