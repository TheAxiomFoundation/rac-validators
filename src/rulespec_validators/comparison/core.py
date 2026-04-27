"""Core record-by-record comparison logic."""

from datetime import datetime

import numpy as np

# Conditional imports
try:
    from policyengine_us import Microsimulation  # pragma: no cover

    HAS_POLICYENGINE = True  # pragma: no cover
except ImportError:
    HAS_POLICYENGINE = False
    Microsimulation = None


def compare_records(
    rulespec_values: np.ndarray,
    pe_values: np.ndarray,
    tolerance: float = 1.0,
    top_n_mismatches: int = 10,
) -> dict:
    """Compare RuleSpec vs PolicyEngine values record-by-record.

    Args:
        rulespec_values: Array of RuleSpec-computed values
        pe_values: Array of PolicyEngine values
        tolerance: Maximum difference to consider a match (in dollars)
        top_n_mismatches: Number of worst mismatches to return

    Returns:
        Dict with match_rate, MAE, error distribution, worst mismatches
    """
    assert len(rulespec_values) == len(pe_values), "Arrays must have same length"

    n_records = len(rulespec_values)
    abs_errors = np.abs(rulespec_values - pe_values)

    # Match rate
    matches = abs_errors <= tolerance
    n_matches = int(np.sum(matches))
    n_mismatches = n_records - n_matches
    match_rate = n_matches / n_records if n_records > 0 else 0.0

    # Error stats
    mean_absolute_error = float(np.mean(abs_errors))
    max_error = float(np.max(abs_errors))

    # Error percentiles
    error_percentiles = {
        "p50": float(np.percentile(abs_errors, 50)),
        "p90": float(np.percentile(abs_errors, 90)),
        "p95": float(np.percentile(abs_errors, 95)),
        "p99": float(np.percentile(abs_errors, 99)),
        "max": max_error,
    }

    # Worst mismatches
    worst_indices = np.argsort(abs_errors)[-top_n_mismatches:][::-1]
    worst_mismatches = []
    for idx in worst_indices:
        if abs_errors[idx] > tolerance:
            worst_mismatches.append(
                {
                    "index": int(idx),
                    "rulespec": float(rulespec_values[idx]),
                    "policyengine": float(pe_values[idx]),
                    "difference": float(abs_errors[idx]),
                }
            )

    return {
        "n_records": n_records,
        "n_matches": n_matches,
        "n_mismatches": n_mismatches,
        "match_rate": match_rate,
        "mean_absolute_error": mean_absolute_error,
        "error_percentiles": error_percentiles,
        "worst_mismatches": worst_mismatches,
        "tolerance": tolerance,
    }


def load_pe_values(variable: str, year: int = 2024, return_ids: bool = False):
    """Load PolicyEngine values for a variable across CPS.

    Args:
        variable: PolicyEngine variable name
        year: Tax year
        return_ids: If True, return (values, tax_unit_ids) tuple

    Returns:
        Array of values for each tax unit, or (values, ids) tuple
    """
    if not HAS_POLICYENGINE:
        raise ImportError("policyengine_us not installed")

    sim = Microsimulation()
    values = np.array(sim.calculate(variable, year))

    if return_ids:
        ids = np.array(sim.calculate("tax_unit_id", year))
        return values, ids
    return values


def load_rulespec_values(variable: str, year: int = 2024, return_ids: bool = False):
    """Load RuleSpec-computed values for a variable across CPS.

    Uses the rules-us runner infrastructure to compute values
    using the same tax unit construction as PolicyEngine comparison.

    Args:
        variable: Variable name (e.g., 'eitc', 'income_tax', 'ctc')
        year: Tax year
        return_ids: If True, return (values, tax_unit_ids) tuple

    Returns:
        Array of values for each tax unit, or (values, ids) tuple

    Raises:
        ImportError: If rules-us not available
    """
    import sys
    from pathlib import Path

    # Add rules-us to path
    data_sources_path = Path.home() / "TheAxiomFoundation" / "rules-us" / "micro" / "us"
    if not data_sources_path.exists():
        raise ImportError(
            f"rules-us not found at {data_sources_path}. "
            "Clone the repo to ~/TheAxiomFoundation/rules-us"
        )
    sys.path.insert(0, str(data_sources_path))

    from rulespec_runner import run_all_calculations
    from tax_unit_builder import load_and_build_tax_units

    # Load and compute
    df = load_and_build_tax_units(year)
    df = run_all_calculations(df, year)

    # Map variable names to rulespec column names
    column_map = {
        "eitc": "rulespec_eitc",
        "ctc": "rulespec_ctc_total",
        "non_refundable_ctc": "rulespec_ctc_nonref",
        "refundable_ctc": "rulespec_ctc_ref",
        "income_tax": "rulespec_income_tax",
        "income_tax_before_credits": "rulespec_income_tax",
        "self_employment_tax": "rulespec_se_tax",
        "net_investment_income_tax": "rulespec_niit",
        "adjusted_gross_income": "adjusted_gross_income",
        "taxable_income": "taxable_income",
    }

    col = column_map.get(variable, f"rulespec_{variable}")
    if col not in df.columns:
        raise ValueError(f"Variable '{variable}' not found. Available: {list(column_map.keys())}")

    values = np.array(df[col].values)

    if return_ids:
        ids = np.array(df["tax_unit_id"].values)
        return values, ids
    return values


def align_records(rulespec_values: np.ndarray, rulespec_ids: np.ndarray, pe_values: np.ndarray, pe_ids: np.ndarray):
    """Align records by tax_unit_id for comparison.

    Uses vectorized merge via sorted index lookup for performance.

    Args:
        rulespec_values: RuleSpec computed values
        rulespec_ids: RuleSpec tax unit IDs
        pe_values: PolicyEngine computed values
        pe_ids: PolicyEngine tax unit IDs

    Returns:
        Tuple of (aligned_rulespec_values, aligned_pe_values, matched_ids)
    """
    # Find common IDs using set intersection
    rulespec_id_set = set(rulespec_ids)
    pe_id_set = set(pe_ids)
    common_ids = np.array(sorted(rulespec_id_set & pe_id_set))

    if len(common_ids) == 0:
        raise ValueError("No matching tax unit IDs between RuleSpec and PolicyEngine")

    # Create lookup dictionaries (O(n) construction, O(1) lookup)
    rulespec_lookup = dict(zip(rulespec_ids, rulespec_values))
    pe_lookup = dict(zip(pe_ids, pe_values))

    # Vectorized value extraction
    aligned_rulespec = np.array([rulespec_lookup[id_] for id_ in common_ids])
    aligned_pe = np.array([pe_lookup[id_] for id_ in common_ids])

    return aligned_rulespec, aligned_pe, common_ids


def run_variable_comparison(
    variable: str,
    year: int = 2024,
    tolerance: float = 1.0,
) -> dict:
    """Run full comparison for a single variable.

    Aligns records by tax_unit_id before comparing.

    Args:
        variable: Variable name to compare
        year: Tax year
        tolerance: Match tolerance in dollars

    Returns:
        Comparison result dict
    """
    # Load with IDs for alignment
    pe_values, pe_ids = load_pe_values(variable, year, return_ids=True)
    rulespec_values, rulespec_ids = load_rulespec_values(variable, year, return_ids=True)

    # Align records
    aligned_rulespec, aligned_pe, matched_ids = align_records(rulespec_values, rulespec_ids, pe_values, pe_ids)

    result = compare_records(aligned_rulespec, aligned_pe, tolerance=tolerance)
    result["variable"] = variable
    result["year"] = year
    result["total_rulespec_records"] = len(rulespec_values)
    result["total_pe_records"] = len(pe_values)
    result["matched_records"] = len(matched_ids)

    return result


def run_full_comparison(
    variables: list[str] | None = None,
    year: int = 2024,
    tolerance: float = 1.0,
) -> dict:
    """Run comparison across all variables.

    Args:
        variables: List of variables to compare (default: common tax variables)
        year: Tax year
        tolerance: Match tolerance in dollars

    Returns:
        Dashboard-formatted comparison results
    """
    if variables is None:
        variables = [
            "eitc",
            "income_tax_before_credits",
            "adjusted_gross_income",
        ]

    results = []
    for var in variables:
        try:
            result = run_variable_comparison(var, year, tolerance)
            results.append(result)
            print(f"  {var}: {result['match_rate'] * 100:.1f}% match rate")
        except Exception as e:
            print(f"  {var}: ERROR - {e}")
            results.append(
                {
                    "variable": var,
                    "year": year,
                    "error": str(e),
                    "match_rate": 0,
                    "n_records": 0,
                }
            )

    return generate_dashboard_json(results, year)


def generate_dashboard_json(results: list[dict], year: int = 2024) -> dict:
    """Generate dashboard JSON from comparison results.

    Args:
        results: List of variable comparison results
        year: Tax year

    Returns:
        Dashboard-formatted dict
    """
    # Overall summary
    total_records = sum(r.get("n_records", 0) for r in results)
    total_matches = sum(r.get("n_records", 0) * r.get("match_rate", 0) for r in results)
    overall_match_rate = total_matches / total_records if total_records > 0 else 0.0

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "tax_year": year,
            "data_source": "CPS ASEC (Enhanced)",
            "comparison": "RuleSpec vs PolicyEngine-US",
        },
        "summary": {
            "overall_match_rate": overall_match_rate,
            "total_records": total_records,
            "n_variables": len(results),
        },
        "variables": results,
    }
