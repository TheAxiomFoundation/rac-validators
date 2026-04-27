"""Import validation for .yaml files.

Checks that all imports reference existing files and variables.
Format: path#variable or path#variable as alias
"""

# NOTE: This may move to rulespec-compile. See docs/scope.md.

import re
from pathlib import Path

from .. import QualityIssue

# Pattern to match imports section
IMPORTS_START = re.compile(r"^\s*imports:")
# Pattern to match individual import
IMPORT_PATTERN = re.compile(
    r"""
    ^\s*-\s*
    (?:['"])?                           # Optional quote
    ([a-zA-Z0-9_/]+)                    # Path (e.g., 26/32/a)
    \#                                  # Hash separator
    (\w+)                               # Variable name
    (?:\s+as\s+(\w+))?                  # Optional alias
    (?:['"])?                           # Optional quote
    """,
    re.VERBOSE,
)


def check_imports(rulespec_files: list[Path], statute_root: Path) -> tuple[list[QualityIssue], bool]:
    """Check that all imports are valid.

    Args:
        rulespec_files: List of .yaml files to check
        statute_root: Root directory for resolving import paths

    Returns:
        Tuple of (issues, all_valid)
    """
    issues: list[QualityIssue] = []
    all_valid = True

    # Build index of all variables in all files
    variable_index: dict[str, set[str]] = {}  # path -> set of variable names

    for rulespec_file in rulespec_files:
        try:
            content = rulespec_file.read_text()
            # Get relative path from statute root
            try:
                rel_path = rulespec_file.relative_to(statute_root)
                # Convert to import format: statute/26/32/a.yaml -> 26/32/a
                path_key = str(rel_path.with_suffix("")).replace("\\", "/")
                # Also handle if statute_root already includes 'statute'
                if path_key.startswith("statute/"):
                    path_key = path_key[8:]
            except ValueError:
                # File not under statute_root, use filename
                path_key = rulespec_file.stem

            # Find all variable declarations
            variables = set()
            for match in re.finditer(r"^variable\s+(\w+):", content, re.MULTILINE):
                variables.add(match.group(1))

            variable_index[path_key] = variables
        except Exception:
            continue

    # Now check imports in each file
    for rulespec_file in rulespec_files:
        try:
            content = rulespec_file.read_text()
            lines = content.split("\n")
        except Exception:
            continue

        in_imports = False

        for i, line in enumerate(lines, 1):
            # Check for imports section start
            if IMPORTS_START.match(line):
                in_imports = True
                continue

            # Exit imports section when we hit non-indented line
            if in_imports and line.strip() and not line.startswith(" "):
                in_imports = False
                continue

            # Parse import
            if in_imports:
                import_match = IMPORT_PATTERN.match(line)
                if import_match:
                    import_path = import_match.group(1)
                    var_name = import_match.group(2)

                    # Check if path exists
                    # Try different file extensions
                    found_file = False
                    for suffix in [".yaml", ""]:
                        check_path = statute_root / f"{import_path}{suffix}"
                        if check_path.exists():
                            found_file = True
                            break
                        # Also try with statute/ prefix
                        check_path = statute_root / "statute" / f"{import_path}{suffix}"
                        if check_path.exists():
                            found_file = True
                            break

                    if not found_file and import_path not in variable_index:
                        issues.append(
                            QualityIssue(
                                file=str(rulespec_file),
                                line=i,
                                category="import",
                                severity="warning",
                                message=f"Import path '{import_path}' does not exist.",
                            )
                        )
                        all_valid = False
                        continue

                    # Check if variable exists in that file
                    if import_path in variable_index and var_name not in variable_index[import_path]:
                        issues.append(
                            QualityIssue(
                                file=str(rulespec_file),
                                line=i,
                                category="import",
                                severity="warning",
                                message=f"Variable '{var_name}' not found in '{import_path}'.",
                            )
                        )
                        all_valid = False

    return issues, all_valid
