from app.models.fusion import FusionInput
from app.services.fusion_scoring_service import compute_layered_score


def _input(affinity: float) -> FusionInput:
    return FusionInput(
        query_id="candidate-1",
        job_id=f"job-{affinity}",
        bm25_score=0.9,
        semantic_score=0.9,
        skill_coverage=0.8,
        graph_relatedness=0.7,
        job_family_match=affinity,
    )


def test_role_gate_keeps_same_family_and_suppresses_cross_family():
    exact = compute_layered_score(_input(1.0), ability_norm=0.8)
    same_family = compute_layered_score(_input(0.8), ability_norm=0.8)
    adjacent = compute_layered_score(_input(0.4), ability_norm=0.8)
    cross_family = compute_layered_score(_input(0.0), ability_norm=0.8)

    assert exact == same_family
    assert exact > adjacent > cross_family
    assert cross_family <= exact * 0.2 + 1e-9
