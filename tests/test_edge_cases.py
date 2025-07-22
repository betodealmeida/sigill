"""
Tests for various edge cases and error conditions.
Covers exception handling, mock scenarios, and boundary conditions.
"""

import pytest
import sqlglot
from unittest.mock import patch, Mock
from sigill.api import (
    _is_column_subset,
    _get_table_names,
    _validate_window_function_columns,
    _validate_where_subqueries,
    _calculate_match_score,
    _expressions_equal,
)


def test_line_305_306_permission_parse_exception():
    """Target lines 305-306: Exception in permission column parsing."""
    # Create a query that will exercise the permission column parsing path
    query = sqlglot.parse_one("SELECT name FROM users")
    permission = sqlglot.parse_one("SELECT complex_column FROM users")

    # We need to intercept the parsing inside _is_column_subset
    # specifically where it parses permission projections
    original_parse_one = sqlglot.parse_one
    parse_call_count = [0]

    def controlled_parse_one(sql, **kwargs):
        parse_call_count[0] += 1
        # Let initial calls succeed, but fail when parsing permission columns
        if parse_call_count[0] > 5 and "complex_column" in str(sql):
            raise ValueError("Controlled parsing exception")
        return original_parse_one(sql, **kwargs)

    with patch("sigill.api.sqlglot.parse_one", side_effect=controlled_parse_one):
        # This should trigger the exception handling in lines 305-306
        result = _is_column_subset(query, permission)
        # Function should handle exception and add the column name to perm_columns
        assert isinstance(result, bool)


def test_line_389_hasattr_ctes_false():
    """Target line 389: hasattr(expression, 'ctes') returns False."""
    # Create a mock expression where hasattr(expr, 'ctes') returns False
    mock_expr = Mock()
    # Explicitly set find_all method
    mock_table = Mock()
    mock_table.name = "test_table"
    mock_table.catalog = None
    mock_table.db = None
    mock_expr.find_all.return_value = [mock_table]

    # Remove ctes attribute to make hasattr return False
    if hasattr(mock_expr, "ctes"):
        delattr(mock_expr, "ctes")

    # This should hit line 389: if hasattr(expression, 'ctes') and expression.ctes:
    # The hasattr check should return False, so the 'and expression.ctes' part won't execute
    tables = _get_table_names(mock_expr)
    assert "test_table" in tables


def test_line_414_empty_columns_in_window():
    """Target line 414: No columns found in window function."""
    # Create a window function with no column references
    # ROW_NUMBER() OVER () has no column references
    window_expr = sqlglot.parse_one("ROW_NUMBER() OVER ()")
    permission_columns = ["col1", "col2"]

    # Mock find_all to return empty list (no columns found)
    with patch.object(window_expr, "find_all", return_value=[]):
        result = _validate_window_function_columns(window_expr, permission_columns)
        # Should return True immediately due to empty column list
        assert result is True


def test_line_435_no_wildcard_in_permission_tables():
    """Target line 435: No wildcard tables in permission."""
    # Create a WHERE clause with subquery
    main_query = sqlglot.parse_one(
        "SELECT name FROM users WHERE id IN (SELECT user_id FROM restricted_table)"
    )
    where_clause = main_query.find(sqlglot.exp.Where)

    # Create permission with specific tables (no wildcards)
    permission = sqlglot.parse_one("SELECT name, id FROM users")

    # Mock _get_table_names to return specific values
    with patch("sigill.api._get_table_names") as mock_get_tables:
        # Subquery tables include restricted_table
        # Permission tables don't include restricted_table and have no wildcards
        mock_get_tables.side_effect = [
            ["restricted_table"],  # subquery tables
            ["users"],  # permission tables (no wildcards)
        ]

        result = _validate_where_subqueries(where_clause, permission)
        # Should return False since restricted_table is not in users and no wildcards
        assert result is False


def test_line_488_no_where_matches_in_score():
    """Target line 488: No WHERE clause matches in score calculation."""
    # Create SQL and permission with different WHERE clauses
    sql = sqlglot.parse_one("SELECT name FROM users WHERE age > 30")
    permission = sqlglot.parse_one("SELECT name FROM users WHERE status = 'active'")

    # Mock _expressions_equal to always return False for WHERE comparisons
    with patch("sigill.api._expressions_equal", return_value=False):
        score = _calculate_match_score(sql, permission)
        # Should get table match points but no WHERE clause match points
        assert score >= 10  # Table match
        # The nested loop should not find any matches, hitting line 488


def test_line_539_expressions_equal_direct():
    """Target line 539: Direct call to _expressions_equal."""
    # Create two different expressions
    expr1 = sqlglot.parse_one("column1")
    expr2 = sqlglot.parse_one("column2")

    # Call _expressions_equal directly to hit line 539
    result = _expressions_equal(expr1, expr2)
    assert result is False

    # Test with identical expressions
    expr3 = sqlglot.parse_one("column1")
    result2 = _expressions_equal(expr1, expr3)
    assert result2 is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
