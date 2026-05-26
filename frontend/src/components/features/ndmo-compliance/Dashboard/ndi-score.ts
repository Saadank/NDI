/**
 * Client-side mirror of the backend NDI scoring formula.
 *
 * Backend source of truth:
 *   backend/app/products/ndmo_compliance/scoring/formula.py
 *
 * Kept in sync manually — if PRIORITY_WEIGHT or the formula changes server-side,
 * update this file too.  Both sides use the SAME weights so the dashboard
 * preview matches the persisted scores.
 */
import type { AssessmentListItem } from "@/lib/types/ndmo-compliance";

const PRIORITY_WEIGHT: Record<1 | 2 | 3, number> = {
  1: 3.0,
  2: 2.0,
  3: 1.0,
};

const MAX_MATURITY = 5;

export interface NdiBreakdown {
  score_percent: number;
  spec_count: number;
  assessed_count: number;
  average_maturity: number;
  per_domain: Record<string, number>;
  per_priority: Record<1 | 2 | 3, number>;
  per_level: Record<0 | 1 | 2 | 3 | 4 | 5, number>;
}

export function computeNdiBreakdown(items: AssessmentListItem[]): NdiBreakdown {
  if (items.length === 0) {
    return {
      score_percent: 0,
      spec_count: 0,
      assessed_count: 0,
      average_maturity: 0,
      per_domain: {},
      per_priority: { 1: 0, 2: 0, 3: 0 },
      per_level: { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
    };
  }

  let weightedActual = 0;
  let weightedMax = 0;

  const perDomainAcc = new Map<string, { actual: number; max: number }>();
  const perPriorityAcc: Record<1 | 2 | 3, { actual: number; max: number }> = {
    1: { actual: 0, max: 0 },
    2: { actual: 0, max: 0 },
    3: { actual: 0, max: 0 },
  };
  const perLevel: Record<0 | 1 | 2 | 3 | 4 | 5, number> = {
    0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
  };

  for (const it of items) {
    const w = PRIORITY_WEIGHT[it.priority] ?? 1.0;
    const actual = w * it.maturity_level;
    const max = w * MAX_MATURITY;

    weightedActual += actual;
    weightedMax += max;

    const dom = perDomainAcc.get(it.domain_code) ?? { actual: 0, max: 0 };
    dom.actual += actual;
    dom.max += max;
    perDomainAcc.set(it.domain_code, dom);

    const prio = perPriorityAcc[it.priority];
    if (prio) {
      prio.actual += actual;
      prio.max += max;
    }

    perLevel[it.maturity_level] = (perLevel[it.maturity_level] ?? 0) + 1;
  }

  const per_domain: Record<string, number> = {};
  for (const [code, { actual, max }] of perDomainAcc) {
    per_domain[code] = max > 0 ? Number(((actual / max) * 100).toFixed(2)) : 0;
  }

  const per_priority: Record<1 | 2 | 3, number> = {
    1: perPriorityAcc[1].max > 0 ? Number(((perPriorityAcc[1].actual / perPriorityAcc[1].max) * 100).toFixed(2)) : 0,
    2: perPriorityAcc[2].max > 0 ? Number(((perPriorityAcc[2].actual / perPriorityAcc[2].max) * 100).toFixed(2)) : 0,
    3: perPriorityAcc[3].max > 0 ? Number(((perPriorityAcc[3].actual / perPriorityAcc[3].max) * 100).toFixed(2)) : 0,
  };

  const score_percent = weightedMax > 0
    ? Number(((weightedActual / weightedMax) * 100).toFixed(2))
    : 0;

  const average_maturity = Number(
    (items.reduce((s, it) => s + it.maturity_level, 0) / items.length).toFixed(2),
  );

  return {
    score_percent,
    spec_count: items.length,
    assessed_count: items.filter((it) => it.maturity_level > 0).length,
    average_maturity,
    per_domain,
    per_priority,
    per_level: perLevel,
  };
}
