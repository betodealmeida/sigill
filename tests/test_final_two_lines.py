"""
Final surgical test to achieve exactly 100% code coverage.
Targets the last 2 uncovered lines: 237, 716
"""

import pytest
import sqlglot
from sigill.api import _matches_three_part_wildcard, _find_matching_expression


def test_line_237_three_part_wildcard_final_return_false():
    """
    Test line 237: The final 'return False' in _matches_three_part_wildcard.

    This line is hit when all SQL tables fail to match the three-part wildcard conditions.
    We need tables that don't match the catalog.db.table pattern.
    """
    # Create SQL tables that won't match the three-part permission pattern
    sql_tables = {
        "wrong_catalog.wrong_db.wrong_table",
        "other_cat.other_db.other_table",
    }

    # Create permission parts: specific names that don't match any SQL table parts
    perm_parts = [
        "target_catalog",
        "target_db",
        "target_table",
    ]  # catalog, db, table - specific names

    # This should go through the loop:
    # For "wrong_catalog.wrong_db.wrong_table":
    # - catalog != "*", so continues to loop
    # - sql_parts = ["wrong_catalog", "wrong_db", "wrong_table"]
    # - len(sql_parts) == 3, checks _parts_match -> should return False (no wildcards, different names)
    # - len(sql_parts) != 2, so second condition fails
    # - len(sql_parts) != 1, so third condition fails
    # - Continue to next table
    #
    # For "other_cat.other_db.other_table":
    # - Similar logic, won't match any conditions
    #
    # No table matches any condition, loop completes, hits line 237: return False

    result = _matches_three_part_wildcard(sql_tables, perm_parts)
    assert result is False


def test_line_716_find_matching_expression_final_return_none():
    """
    Test line 716: The final 'return None' in _find_matching_expression.

    This line is hit when:
    1. perm_expr is not a Column
    2. perm_expr is not an ANONYMIZE expression
    3. None of the SQL expressions equal the permission expression
    4. The loop completes without finding a match
    """
    # Create a permission expression that's not a Column and not ANONYMIZE
    # Use a simple literal expression
    perm_expr = sqlglot.parse_one("'literal_string'")

    # Create SQL expressions that don't match
    sql_expressions = [
        sqlglot.parse_one("column_name"),
        sqlglot.parse_one("42"),
        sqlglot.parse_one("'different_string'"),
    ]

    # This should:
    # 1. Check isinstance(perm_expr, sqlglot.exp.Column) -> False
    # 2. Check _is_anonymize_expression(perm_expr) -> False
    # 3. Loop through sql_expressions, none equal 'literal_string'
    # 4. Hit line 716: return None

    result = _find_matching_expression(perm_expr, sql_expressions)
    assert result is None


def test_combined_final_coverage_scenarios():
    """Test both edge cases in combination to ensure complete coverage."""

    # Test 1: Three-part wildcard scenarios that should hit line 237
    # Case 1a: Tables with 3 parts that don't match permission parts
    sql_tables_1a = {"wrong_cat.wrong_db.wrong_table", "bad_cat.bad_db.bad_table"}
    perm_parts_1a = ["correct_cat", "correct_db", "correct_table"]
    result_1a = _matches_three_part_wildcard(sql_tables_1a, perm_parts_1a)
    assert result_1a is False

    # Case 1b: Tables with 2 parts where db != "*"
    sql_tables_1b = {"some_db.some_table"}
    perm_parts_1b = ["specific_cat", "other_db", "any_table"]  # db != "*"
    result_1b = _matches_three_part_wildcard(sql_tables_1b, perm_parts_1b)
    assert result_1b is False

    # Case 1c: Single-part table without proper wildcards
    sql_tables_1c = {"single_table"}
    perm_parts_1c = ["cat", "db", "table"]  # db != "*" or table != "*"
    result_1c = _matches_three_part_wildcard(sql_tables_1c, perm_parts_1c)
    assert result_1c is False

    # Test 2: Find matching expression with incompatible types
    perm_expr_2 = sqlglot.parse_one("123")  # Numeric literal
    sql_expressions_2 = [
        sqlglot.parse_one("column_a"),
        sqlglot.parse_one("'string_value'"),  # Different literal type
        sqlglot.parse_one("456"),  # Different numeric value
    ]
    result_2 = _find_matching_expression(perm_expr_2, sql_expressions_2)
    assert result_2 is None

    # Test 3: More complex non-matching scenario
    perm_expr_3 = sqlglot.parse_one("UPPER('test')")  # Function expression
    sql_expressions_3 = [
        sqlglot.parse_one("LOWER('test')"),  # Different function
        sqlglot.parse_one("'test'"),  # Different expression type
        sqlglot.parse_one("column_name"),  # Column vs function
    ]
    result_3 = _find_matching_expression(perm_expr_3, sql_expressions_3)
    assert result_3 is None


def test_line_237_exhaustive_scenarios():
    """Exhaustive test to ensure line 237 is definitely hit."""

    # Scenario 1: 3-part tables that don't match due to different names
    result_1 = _matches_three_part_wildcard(
        {"cat1.db1.table1", "cat2.db2.table2"},
        ["different_cat", "different_db", "different_table"],
    )
    assert result_1 is False

    # Scenario 2: 2-part table where db condition fails
    result_2 = _matches_three_part_wildcard(
        {"some_db.some_table"}, ["cat_name", "other_db", "table_name"]  # db != "*"
    )
    assert result_2 is False

    # Scenario 3: Single-part table where conditions fail
    result_3 = _matches_three_part_wildcard(
        {"simple_table"}, ["cat", "db", "table"]  # db != "*" and table != "*"
    )
    assert result_3 is False

    # Scenario 4: Empty table set (edge case)
    result_4 = _matches_three_part_wildcard(set(), ["any_cat", "any_db", "any_table"])
    assert result_4 is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
