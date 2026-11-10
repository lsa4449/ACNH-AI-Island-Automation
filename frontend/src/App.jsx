import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import BlueprintCanvas from "./BlueprintCanvas.jsx";

const box = { background: "#fff", borderRadius: 12, padding: 16, marginBottom: 16 };

export default function App() {
  const [health, setHealth] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [zones, setZones] = useState([]);
  const [zone, setZone] = useState(null);
  const [prompt, setPrompt] = useState("꽃길과 나무가 있는 작은 공원");
  const [useLlm, setUseLlm] = useState(true);
  const [design, setDesign] = useState(null);
  const [plan, setPlan] = useState(null);
  const [run, setRun] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const guard = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    guard(async () => {
      const [h, c, z] = await Promise.all([api.health(), api.catalog(), api.zones()]);
      setHealth(h);
      setCatalog(c);
      setZones(z);
      if (z.length) setZone(z[z.length - 1]);
    });
  }, []);

  const addSample = () => guard(async () => {
    const z = await api.createSampleZone();
    setZones((prev) => [...prev, z]);
    setZone(z);
    setDesign(null); setPlan(null); setRun(null);
  });

  const generate = () => guard(async () => {
    const d = await api.createDesign(zone.id, prompt, useLlm);
    setDesign(d);
    setPlan(await api.plan(d.id));
    setRun(null);
  });

  const simulate = (dryRun) => guard(async () => setRun(await api.run(design.id, dryRun)));
  const name = (id) => catalog.find((i) => i.id === id)?.name_ko ?? id;

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1 style={{ fontSize: 22 }}>ACNH AI Island Designer <small style={{ fontWeight: 400 }}>Phase 1 · 시뮬레이션 전용</small></h1>
      {error && <div style={{ ...box, background: "#fde2e2" }}>{error}</div>}

      <div style={box}>
        <b>Ollama:</b>{" "}
        {health ? (health.ollama.available ? `연결됨 (${health.ollama.model})` : "연결 안 됨 → 규칙 기반 생성기 사용") : "확인 중"}
        {" · "}<b>컨트롤러:</b> mock
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select value={zone?.id ?? ""} onChange={(e) => { setZone(zones.find((z) => z.id === e.target.value)); setDesign(null); setPlan(null); setRun(null); }}>
            {!zones.length && <option value="">구역 없음</option>}
            {zones.map((z) => <option key={z.id} value={z.id}>{z.name} ({z.width}×{z.height})</option>)}
          </select>
          <button onClick={addSample} disabled={busy}>10×10 샘플 구역 추가</button>
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input style={{ flex: 1, minWidth: 240, padding: 6 }} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          <label><input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} /> LLM 사용</label>
          <button onClick={generate} disabled={busy || !zone || !prompt.trim()}>설계 생성</button>
        </div>
      </div>

      {zone && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
          <div style={{ ...box, overflowX: "auto" }}>
            <BlueprintCanvas zone={zone} design={design} catalog={catalog} plan={plan} />
          </div>
          {design && (
            <div style={{ ...box, flex: 1, minWidth: 280 }}>
              <p><b>생성 방식:</b> {design.source}{design.model ? ` (${design.model})` : ""}</p>
              {design.notes && <p>{design.notes}</p>}
              <p><b>배치:</b> {design.placements.length}개 · <b>거부:</b> {design.rejected.length}개</p>
              <ul>{design.rejected.map((r, i) => <li key={i}>{name(r.placement.item_id)} ({r.placement.x},{r.placement.y}): {r.message}</li>)}</ul>
              {plan && (
                <>
                  <p><b>필요 아이템</b></p>
                  <ul>{Object.entries(plan.required_items).map(([id, n]) => <li key={id}>{name(id)} × {n}</li>)}</ul>
                  <p>작업 {plan.tasks.length}개 · 이동 {plan.total_steps}칸 · 사용자 개입 필요 {plan.needs_user}개</p>
                </>
              )}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button onClick={() => simulate(true)} disabled={busy}>Dry Run</button>
                <button onClick={() => simulate(false)} disabled={busy}>Mock 실행</button>
                <button onClick={() => guard(api.stop)}>긴급 정지</button>
                <button onClick={() => guard(api.reset)}>정지 해제</button>
              </div>
              {run && <p><b>{run.dry_run ? "Dry Run" : "Mock 실행"}:</b> {run.status} · 명령 {run.commands.length}개 · 완료 작업 {run.completed_tasks.length}개 {run.message}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
