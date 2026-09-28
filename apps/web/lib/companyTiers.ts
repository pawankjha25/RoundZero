// Cosmetic-only interview-complexity tiers an admin can tag a company with
// (apps/api/models.py::CompanyProfileOption.tier) - purely a display/
// organization label. Does not change interviewer behavior, rubric
// weighting, or anything the candidate experiences; a real per-tier
// interviewer persona is a separate, bigger, not-yet-decided project.
export interface CompanyTier {
  value: string;
  label: string;
}

export const COMPANY_TIERS: CompanyTier[] = [
  { value: "frontier_ai_labs", label: "Frontier AI labs" },
  { value: "big_tech", label: "Big Tech / FAANG+" },
  { value: "growth_stage", label: "Growth-stage" },
  { value: "early_stage", label: "Early-stage" },
  { value: "enterprise_other", label: "Enterprise / other" },
];

export function companyTierLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  return COMPANY_TIERS.find((t) => t.value === value)?.label ?? value;
}
