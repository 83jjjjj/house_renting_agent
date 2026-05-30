from tests.eval_scripts.run_e2e_eval import infer_final_route, score_case


def test_infer_final_route_prefers_created_order():
    assert infer_final_route({"user_intent": "recommend"}, after_orders=2, before_orders=1) == "reserve"


def test_score_case_passes_expected_business_checks():
    case = {
        "expected": {
            "final_route": "reserve",
            "must_visit": ["determine_user_intent", "reserve"],
            "has_order": True,
        }
    }
    result = {"user_intent": "reserve", "visited": ["determine_user_intent", "reserve"]}
    run_meta = {"before_orders": 0, "after_orders": 1, "error": None, "unused_turns": 0}

    scores = score_case(case, result, run_meta)

    assert scores["passed"]
    assert scores["failures"] == []


def test_score_case_reports_missing_visits():
    case = {
        "expected": {
            "final_route": "recommend",
            "must_visit": ["determine_user_intent", "collect_user_demand"],
        }
    }
    result = {"user_intent": "recommend", "visited": ["determine_user_intent"]}
    run_meta = {"before_orders": 0, "after_orders": 0, "error": None, "unused_turns": 0}

    scores = score_case(case, result, run_meta)

    assert not scores["passed"]
    assert scores["missing_visits"] == ["collect_user_demand"]
    assert "must_visit" in scores["failures"]
