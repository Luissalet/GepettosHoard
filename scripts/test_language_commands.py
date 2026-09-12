"""Real local-model edit tests on an in-memory copy of a grounded project."""

import json, sys, time, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.commands import interpret, apply_operations

p = json.loads((ROOT / "data/a8755b9f6795/project.json").read_text("utf-8"))
out = ROOT / "data/language-evaluation"
out.mkdir(exist_ok=True)


def rows(p):
    return {f"{a['id']}:{r['id']}": r for a in p["assets"] for r in a["regions"]}


before = rows(p)
report = []
cases = [
    ("relative", "Los ojos más hundidos y las pecas con más relieve."),
    (
        "equal",
        "Pon Pecas a la misma altura que Cobertura superior, manteniendo los grupos separados.",
    ),
    ("merge", "Une Pecas y Cobertura superior en un grupo llamado Adornos."),
    (
        "split",
        "Separa las zonas 7 y 18 de mBody_Alb.png del grupo Pecas, con el nombre Pecas laterales.",
    ),
]
for name, instruction in cases:
    sample = copy.deepcopy(p)
    if name == "equal":
        for r in rows(sample).values():
            if r["name"] == "Cobertura superior":
                r["height"] = 150
    start = time.perf_counter()
    plan = interpret("qwen3.8:27b-q4_K_M", instruction, sample, [], out / name)
    q = apply_operations(sample, plan)
    after = rows(q)
    assert not plan.clarification, plan.clarification
    if name == "relative":
        for key, r in before.items():
            assert after[key]["height"] == max(
                0,
                min(
                    255,
                    r["height"]
                    + (-16 if r["name"] == "Ojos" else 16 if r["name"] == "Pecas" else 0),
                ),
            ), key
    elif name == "equal":
        selected = [r for r in after.values() if r["name"] in ["Pecas", "Cobertura superior"]]
        assert (
            len({r["heightGroup"] for r in selected}) == 1
            and len({r["semanticGroup"] for r in selected}) == 2
            and {r["height"] for r in selected} == {150}
        )
    elif name == "merge":
        selected = [r for r in after.values() if r["name"] == "Adornos"]
        assert len(selected) == 13 and len({r["semanticGroup"] for r in selected}) == 1
    elif name == "split":
        selected = [r for r in after.values() if r["name"] == "Pecas laterales"]
        assert len(selected) == 2
        assert all(r["semanticGroup"] != after["b8f146fcbe:2"]["semanticGroup"] for r in selected)
    entry = {
        "case": name,
        "instruction": instruction,
        "seconds": round(time.perf_counter() - start, 2),
        "passed": True,
        "plan": plan.model_dump(),
    }
    report.append(entry)
    print(json.dumps(entry, ensure_ascii=False), flush=True)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
assert rows(p) == before
