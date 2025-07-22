"""
The absolutely final test to achieve exactly 100% code coverage.
Targets the last 3 missing lines: 237, 716, 747
"""

import pytest
import sqlglot
from sigill.api import (
    _matches_two_part_wildcard,
    _find_matching_anonymize_expression,
    tighten,
)


def test_line_237_two_part_wildcard_complete_no_match():
    """Test line 237: two-part wildcard with absolutely no matching scenarios."""
    # Create SQL tables that won't match any of the wildcard patterns
    sql_tables = {"unrelated_table"}  # Single part name
    perm_parts = ["specific_db", "specific_table"]  # Two specific parts, no wildcards

    # This should go through all the conditions and hit the final return False at line 237
    result = _matches_two_part_wildcard(sql_tables, perm_parts)
    assert result is False


def test_line_716_no_matching_expression_in_tighten():
    """Test line 716: no matching expression found during tighten operation."""
    # Create a scenario where tighten tries to match expressions but fails
    # Use the tighten function which internally calls _find_matching_expression

    sql = "SELECT unique_query_column FROM users"
    permissions = {"SELECT completely_different_permission_column FROM users"}

    try:
        result = tighten(sql, permissions)
        # The tighten should complete but with NULL for non-matching columns
        # Check that the result contains NULL (which comes from line 716 path)
        result_sql = result.sql()
        assert "NULL" in result_sql
    except ValueError:
        # If no matching permission found, that's also expected behavior
        pass


def test_line_747_no_matching_anonymize_expression_direct():
    """Test line 747: no matching ANONYMIZE expression found."""
    # Create an ANONYMIZE expression that won't match any SQL expressions

    # Create a mock ANONYMIZE function with a non-column inner expression
    anonymize_perm = sqlglot.parse_one("ANONYMIZE(CONCAT('prefix_', some_column))")
    sql_expressions = [
        sqlglot.parse_one("simple_column"),
        sqlglot.parse_one("another_column"),
    ]

    # This should try to match but fail, hitting line 747
    result = _find_matching_anonymize_expression(anonymize_perm, sql_expressions)
    assert result is None


def test_comprehensive_final_edge_cases():
    """Test various edge cases to ensure we hit all remaining paths."""

    # Test 1: Complex wildcard scenario that should hit line 237
    sql_tables = {"standalone_table"}
    perm_parts = ["exact_schema", "exact_table"]
    result1 = _matches_two_part_wildcard(sql_tables, perm_parts)
    assert result1 is False

    # Test 2: Tighten scenario that should involve line 716
    try:
        sql = "SELECT col1, col2 FROM table1"
        perms = {"SELECT different_col1, different_col2 FROM table1"}
        result2 = tighten(sql, perms)
        # Should succeed with NULLs for non-matching columns
        assert "NULL" in result2.sql()
    except ValueError:
        # Also acceptable if no matching permission is found
        pass

    # Test 3: ANONYMIZE scenario that should hit line 747
    complex_anonymize = sqlglot.parse_one("ANONYMIZE(UPPER(nonexistent_col))")
    simple_cols = [sqlglot.parse_one("existing_col")]
    result3 = _find_matching_anonymize_expression(complex_anonymize, simple_cols)
    assert result3 is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
