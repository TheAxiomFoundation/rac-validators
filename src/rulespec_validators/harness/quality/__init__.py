"""Quality checks for .yaml files."""

from pathlib import Path
from typing import Optional

from .. import QualityIssue, QualityResult
from .coverage import check_test_coverage
from .grounding import check_grounding
from .imports import check_imports
from .schema import check_schema


def run_quality_checks(
    statute_root: Path,
    changed_files: Optional[list[Path]] = None,
    rule_text: Optional[str] = None,
    rule_text_by_file: Optional[dict[str, str]] = None,
) -> QualityResult:
    """Run all quality checks on .yaml files.

    Args:
        statute_root: Root directory of statute files (e.g., rules-us/statute)
        changed_files: If provided, only check these files. Otherwise check all.

    Returns:
        QualityResult with all findings
    """
    # Find all .yaml files if not specified
    if changed_files is None:
        rulespec_files = list(statute_root.rglob("*.yaml"))
    else:
        rulespec_files = [f for f in changed_files if f.suffix == ".yaml"]

    if not rulespec_files:
        return QualityResult(
            test_coverage=1.0,
            no_literals_pass=True,
            all_imports_valid=True,
            all_dtypes_valid=True,
            all_grounded=True,
            issues=[],
        )

    all_issues: list[QualityIssue] = []

    # Schema checks (entity, period, dtype, no literals)
    schema_issues, no_literals_pass, all_dtypes_valid = check_schema(rulespec_files)
    all_issues.extend(schema_issues)

    # Test coverage
    coverage_rate, coverage_issues = check_test_coverage(rulespec_files)
    all_issues.extend(coverage_issues)

    # Import validation
    import_issues, all_imports_valid = check_imports(rulespec_files, statute_root)
    all_issues.extend(import_issues)

    # Source grounding
    grounding_issues, all_grounded = check_grounding(
        rulespec_files, rule_text=rule_text, rule_text_by_file=rule_text_by_file
    )
    all_issues.extend(grounding_issues)

    return QualityResult(
        test_coverage=coverage_rate,
        no_literals_pass=no_literals_pass,
        all_imports_valid=all_imports_valid,
        all_dtypes_valid=all_dtypes_valid,
        all_grounded=all_grounded,
        issues=all_issues,
    )


__all__ = [
    "run_quality_checks",
    "check_schema",
    "check_test_coverage",
    "check_imports",
    "check_grounding",
]
