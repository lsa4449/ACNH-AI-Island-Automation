import cv2
import numpy as np


def test_health_reports_ollama_down(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["ollama"]["available"] is False and body["dry_run_default"] is True


def test_full_flow_10x10(client):
    zone = client.post("/api/zones/sample").json()
    assert (zone["width"], zone["height"]) == (10, 10)
    r = client.post("/api/designs", json={"zone_id": zone["id"], "prompt": "꽃길이 있는 작은 공원", "seed": 3})
    assert r.status_code == 201
    design = r.json()
    assert design["source"] == "rule_based" and len(design["placements"]) > 5

    assert client.get(f"/api/designs/{design['id']}").json() == design
    assert len(client.get("/api/designs", params={"zone_id": zone["id"]}).json()) == 1

    plan = client.get(f"/api/designs/{design['id']}/plan").json()
    assert len(plan["tasks"]) == len(design["placements"])

    dry = client.post(f"/api/designs/{design['id']}/run", json={}).json()
    assert dry["dry_run"] is True and dry["status"] == "completed"
    sim = client.post(f"/api/designs/{design['id']}/run", json={"dry_run": False}).json()
    assert sim["status"] == "completed" and sim["commands"] == dry["commands"]
    assert len(client.get(f"/api/designs/{design['id']}/runs").json()) == 2


def test_emergency_stop_blocks_runs(client):
    zone = client.post("/api/zones/sample").json()
    design = client.post("/api/designs", json={"zone_id": zone["id"], "prompt": "공원"}).json()
    client.post("/api/runs/stop")
    assert client.post(f"/api/designs/{design['id']}/run", json={}).status_code == 409
    client.post("/api/runs/reset")
    assert client.post(f"/api/designs/{design['id']}/run", json={}).status_code == 200


def test_validation_and_errors(client):
    zone = client.post("/api/zones/sample").json()
    r = client.post("/api/designs/validate", json={"zone_id": zone["id"], "placements": [
        {"item_id": "sapling", "x": 7, "y": 0}]}).json()
    assert r["rejected"][0]["code"] == "TERRAIN_NOT_ALLOWED"
    assert client.get("/api/designs/none").status_code == 404
    assert client.post("/api/designs", json={"zone_id": "none", "prompt": "x"}).status_code == 404
    bad = {"name": "x", "width": 2, "height": 2, "tiles": [["grass"]]}
    assert client.post("/api/zones", json=bad).status_code == 422
    assert client.post("/api/designs/x/run", json={"controller": "esp32"}).status_code == 422


def test_zone_manual_correction(client):
    zone = client.post("/api/zones/sample").json()
    zone["tiles"][9][6] = "grass"
    updated = client.put(f"/api/zones/{zone['id']}", json=zone).json()
    assert updated["tiles"][9][6] == "grass" and updated["id"] == zone["id"]


def test_map_image_draft(client):
    img = np.zeros((100, 100, 3), np.uint8)
    img[:, :50] = (60, 180, 60)    # BGR 초록 → grass
    img[:, 50:] = (200, 120, 40)   # BGR 파랑 → water
    img[75:, 75:] = (128, 128, 128)  # 회색 → unknown
    ok, buf = cv2.imencode(".png", img)
    r = client.post("/api/maps/draft-zone", files={"file": ("m.png", buf.tobytes(), "image/png")},
                    data={"cols": "4", "rows": "4", "name": "초안"})
    assert r.status_code == 201
    z = r.json()
    assert z["tiles"][0] == ["grass", "grass", "water", "water"]
    assert z["tiles"][3][3] == "unknown" and z["confidence"][0][0] == 1.0
    bad = client.post("/api/maps/draft-zone", files={"file": ("m.png", b"not an image", "image/png")},
                      data={"cols": "4", "rows": "4"})
    assert bad.status_code == 400
