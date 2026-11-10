from backend.app.services.ai.designer import build_user_prompt, generate_design
from backend.app.services.planner.validator import validate
from tests.conftest import fake_ollama


def test_rule_based_design_is_valid_and_deterministic(zone, catalog):
    a = generate_design("z", zone, catalog, "꽃길과 나무가 있는 공원", None, use_llm=False, seed=7)
    b = generate_design("z", zone, catalog, "꽃길과 나무가 있는 공원", None, use_llm=False, seed=7)
    assert a.source == "rule_based" and a.placements == b.placements
    cats = {catalog.get(p.item_id).category for p in a.placements}
    assert cats == {"path", "flower", "tree", "furniture"}
    assert not validate(zone, catalog, a.placements).rejected


def test_keywords_limit_categories(zone, catalog):
    d = generate_design("z", zone, catalog, "꽃만 심어줘", None, use_llm=False)
    assert {catalog.get(p.item_id).category for p in d.placements} == {"flower"}


def test_prompt_contains_grid_and_catalog(zone, catalog):
    text = build_user_prompt(zone, catalog, "테스트")
    assert "y=05 ..S......." in text and "garden_bench" in text


def test_ollama_output_is_validated(zone, catalog):
    llm = fake_ollama({"notes": "ok", "placements": [
        {"item_id": "path_stone", "x": 3, "y": 5, "rotation": 0},
        {"item_id": "flower_rose_white", "x": 7, "y": 1, "rotation": 0},  # 물 위 → 거부
    ]})
    d = generate_design("z", zone, catalog, "길", llm)
    assert d.source == "ollama" and d.model == "fake"
    assert len(d.placements) == 1 and d.rejected[0].code == "TERRAIN_NOT_ALLOWED"


def test_fallback_when_ollama_down_or_garbage(zone, catalog):
    down = generate_design("z", zone, catalog, "공원", fake_ollama(None))
    garbage = generate_design("z", zone, catalog, "공원", fake_ollama({"wrong": 1}))
    for d in (down, garbage):
        assert d.source == "rule_based" and d.placements and "대체" in d.notes
