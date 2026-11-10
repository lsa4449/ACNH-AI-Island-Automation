async function call(path, options) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

const post = (path, body) => call(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  health: () => call("/health"),
  catalog: () => call("/catalog"),
  zones: () => call("/zones"),
  createSampleZone: () => post("/zones/sample"),
  createDesign: (zone_id, prompt, use_llm) => post("/designs", { zone_id, prompt, use_llm }),
  plan: (id) => call(`/designs/${id}/plan`),
  run: (id, dry_run) => post(`/designs/${id}/run`, { dry_run }),
  stop: () => post("/runs/stop"),
  reset: () => post("/runs/reset"),
};
