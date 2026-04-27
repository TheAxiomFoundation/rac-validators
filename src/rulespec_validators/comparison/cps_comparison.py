"""
Validate RuleSpec calculations against PolicyEngine on the same CPS data.

This runs both RuleSpec and PolicyEngine calculations on identical inputs
to measure agreement.
"""

import numpy as np
import pandas as pd
from rulespec_runner import run_all_calculations
from policyengine_us import Microsimulation
from tax_unit_builder import load_and_build_tax_units


def get_pe_values(year: int = 2024) -> pd.DataFrame:
    """Get PolicyEngine calculated values for CPS."""
    print("Loading PolicyEngine microsimulation...")
    sim = Microsimulation()

    # Tax unit level variables
    tu_id = np.array(sim.calculate("tax_unit_id", year))

    results = pd.DataFrame(
        {
            "tax_unit_id": tu_id,
            "pe_eitc": np.array(sim.calculate("eitc", year)),
            "pe_ctc_nonref": np.array(sim.calculate("non_refundable_ctc", year)),
            "pe_ctc_ref": np.array(sim.calculate("refundable_ctc", year)),
            "pe_income_tax": np.array(sim.calculate("income_tax_before_credits", year)),
            "pe_se_tax": np.array(sim.calculate("self_employment_tax", year)),
            "pe_niit": np.array(sim.calculate("net_investment_income_tax", year)),
            # Get key inputs for comparison
            "pe_agi": np.array(sim.calculate("adjusted_gross_income", year)),
            "pe_taxable_income": np.array(sim.calculate("taxable_income", year)),
            "pe_earned_income": np.array(sim.calculate("tax_unit_earned_income", year)),
        }
    )

    results["pe_ctc_total"] = results["pe_ctc_nonref"] + results["pe_ctc_ref"]

    return results


def compare_calculations(rulespec_df: pd.DataFrame, pe_df: pd.DataFrame) -> dict:
    """Compare RuleSpec vs PolicyEngine calculations."""

    # Merge on tax_unit_id
    merged = rulespec_df.merge(pe_df, on="tax_unit_id", how="inner")
    print(f"Matched {len(merged):,} tax units")

    results = {}

    # Compare each variable
    comparisons = [
        ("rulespec_eitc", "pe_eitc", "EITC"),
        ("rulespec_ctc_total", "pe_ctc_total", "CTC Total"),
        ("rulespec_se_tax", "pe_se_tax", "SE Tax"),
        ("rulespec_income_tax", "pe_income_tax", "Income Tax"),
        ("rulespec_niit", "pe_niit", "NIIT"),
        ("adjusted_gross_income", "pe_agi", "AGI"),
        ("taxable_income", "pe_taxable_income", "Taxable Income"),
    ]

    print("\n=== RuleSpec vs PolicyEngine Comparison ===\n")
    print(f"{'Variable':<20} {'Match %':>10} {'Mean Diff':>15} {'Corr':>10}")
    print("-" * 60)

    for rulespec_col, pe_col, label in comparisons:
        if rulespec_col not in merged.columns or pe_col not in merged.columns:
            print(f"{label:<20} {'N/A':>10}")
            continue

        rulespec_vals = merged[rulespec_col].values
        pe_vals = merged[pe_col].values

        # Match rate (within $1)
        diff = np.abs(rulespec_vals - pe_vals)
        match_rate = (diff <= 1).mean() * 100

        # Mean difference
        mean_diff = np.mean(rulespec_vals - pe_vals)

        # Correlation (for non-zero values)
        mask = (rulespec_vals > 0) | (pe_vals > 0)
        corr = np.corrcoef(rulespec_vals[mask], pe_vals[mask])[0, 1] if mask.sum() > 10 else np.nan

        print(f"{label:<20} {match_rate:>9.1f}% ${mean_diff:>14,.0f} {corr:>10.4f}")

        results[label] = {
            "match_rate": match_rate,
            "mean_diff": mean_diff,
            "correlation": corr,
        }

    # Weighted totals comparison
    print("\n--- Weighted Totals ---")
    weight = merged["weight"].values

    for rulespec_col, pe_col, label in comparisons[:5]:  # Just tax variables
        if rulespec_col not in merged.columns or pe_col not in merged.columns:
            continue

        rulespec_total = (merged[rulespec_col] * weight).sum()
        pe_total = (merged[pe_col] * weight).sum()
        pct_diff = (rulespec_total - pe_total) / pe_total * 100 if pe_total != 0 else 0

        print(f"{label:<20} RuleSpec: ${rulespec_total:>15,.0f}  PE: ${pe_total:>15,.0f}  ({pct_diff:+.1f}%)")

    return results


def main():
    print("=" * 60)
    print("RuleSpec vs PolicyEngine Validation on CPS Microdata")
    print("=" * 60)

    # Load our tax unit data
    print("\n1. Building tax units from CPS...")
    rulespec_df = load_and_build_tax_units(2024)
    print(f"   Built {len(rulespec_df):,} tax units")

    # Run RuleSpec calculations
    print("\n2. Running RuleSpec calculations...")
    rulespec_df = run_all_calculations(rulespec_df)

    # Get PolicyEngine values
    print("\n3. Loading PolicyEngine calculations...")
    pe_df = get_pe_values(2024)
    print(f"   Got {len(pe_df):,} tax units from PE")

    # Compare
    print("\n4. Comparing results...")
    results = compare_calculations(rulespec_df, pe_df)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Overall assessment
    avg_match = np.mean([r["match_rate"] for r in results.values() if not np.isnan(r.get("match_rate", np.nan))])
    print(f"Average match rate: {avg_match:.1f}%")

    if avg_match >= 90:
        print("✅ EXCELLENT: RuleSpec closely matches PolicyEngine")
    elif avg_match >= 75:
        print("⚠️  GOOD: Minor discrepancies to investigate")
    else:
        print("❌ NEEDS WORK: Significant discrepancies found")


if __name__ == "__main__":  # pragma: no cover
    main()
