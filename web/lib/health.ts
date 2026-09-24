import { API_BASE } from "@/lib/api";

// GET / is the one route that never touches the pipeline (backend/api/main.py).
// Besides readiness it says whether this server permits model-enabled inbox
// runs at all -- SENTINEL_ALLOW_LLM_RUNS, off by default on a public URL --
// which is what the run page needs to know before offering the switch.
export interface ApiHealth {
  service: string;
  status: string;
  data_root: string;
  ready: boolean;
  llm_runs_allowed: boolean;
}

export async function fetchHealth(): Promise<ApiHealth> {
  const res = await fetch(`${API_BASE}/`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET / -> ${res.status}`);
  return (await res.json()) as ApiHealth;
}
