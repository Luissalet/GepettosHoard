from backend.closed_loop import select_candidate


def entry(i, edges, acceptable, issues):
    return {
        "iteration": i,
        "review": {
            "acceptable": acceptable,
            "issues": issues,
            "geometryCheck": {
                "control": {"boundary_edges": 10},
                "current": {"boundary_edges": edges},
            },
        },
    }


def test_visual_self_approval_cannot_outweigh_new_geometry_damage():
    best = select_candidate(
        [entry(0, 10, False, ["Débil"]), entry(1, 32, True, []), entry(2, 15, False, ["Costura"])]
    )
    assert best["iteration"] == 0


def test_no_regression_prefers_accepted_then_latest_equivalent_candidate():
    assert (
        select_candidate([entry(0, 10, False, []), entry(1, 10, True, []), entry(2, 10, True, [])])[
            "iteration"
        ]
        == 2
    )
