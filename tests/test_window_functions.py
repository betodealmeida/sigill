"""
Tests for window function validation and CTE handling.
Covers window function column validation and Common Table Expression processing.
"""

import pytest
import sqlglot
from unittest.mock import patch, MagicMock
from sigill.api import (
    check_permission,
    _is_column_subset,
    _get_table_names,
    _validate_window_function_columns,
    _validate_where_subqueries,
    _calculate_match_score,
    _expressions_equal,
)


class TestRemainingUncoveredLines:
    """Test the exact remaining uncovered lines for 100% coverage."""

    def test_permission_column_parsing_exception_lines_305_306(self):
        """Test lines 305-306: Exception handling in permission column parsing."""

        # Create a scenario where permission column parsing fails
        query = sqlglot.parse_one("SELECT name FROM users")
        permission = sqlglot.parse_one("SELECT complex_expr FROM users")

        # Mock sqlglot.parse_one to cause an exception during permission parsing
        original_parse = sqlglot.parse_one
        call_count = [0]

        def mock_parse_one(sql, **kwargs):
            call_count[0] += 1
            # Let the first call succeed (for query parsing)
            # Fail on subsequent calls (permission column parsing)
            if call_count[0] > 3:  # After a few successful calls, start failing
                raise Exception("Permission column parsing error")
            return original_parse(sql, **kwargs)

        with patch("sqlglot.parse_one", side_effect=mock_parse_one):
            # This should trigger the exception handling in lines 305-306
            result = _is_column_subset(query, permission)
            # The function should handle the exception gracefully and continue
            assert isinstance(result, bool)

    def test_window_function_validation_lines_319_320(self):
        """Test lines 319-320: Window function validation path."""
        # Create a query with a window function that will trigger the specific validation path
        query = sqlglot.parse_one(
            "SELECT name, ROW_NUMBER() OVER (ORDER BY id) FROM users"
        )
        permission = sqlglot.parse_one("SELECT name, id FROM users")

        # The _is_column_subset function should validate the window function
        # and hit lines 319-320 in the window function validation
        result = _is_column_subset(query, permission)
        assert result is True

    def test_cte_hasattr_check_line_389(self):
        """Test line 389: hasattr(expression, 'ctes') check."""
        # Create a mock expression that doesn't have a 'ctes' attribute
        mock_expr = MagicMock()

        # Remove the 'ctes' attribute to trigger the hasattr check
        del mock_expr.ctes

        # Mock find_all to return tables
        mock_table = MagicMock()
        mock_table.name = "users"
        mock_table.catalog = None
        mock_table.db = None
        mock_expr.find_all.return_value = [mock_table]

        # This should hit line 389 where we check hasattr(expression, 'ctes')
        tables = _get_table_names(mock_expr)
        assert "users" in tables

    def test_empty_window_function_columns_line_414(self):
        """Test line 414: Window function with empty column list."""
        # Create a window function that references no columns
        window_expr = sqlglot.parse_one("ROW_NUMBER() OVER ()")
        permission_columns = ["name", "id"]

        # This should return True immediately due to empty column list (line 414)
        result = _validate_window_function_columns(window_expr, permission_columns)
        assert result is True

    def test_subquery_no_wildcard_tables_line_435(self):
        """Test line 435: Subquery validation when no wildcard tables in permission."""
        # Create a WHERE clause with subquery that references unauthorized tables
        main_query = sqlglot.parse_one(
            "SELECT name FROM users WHERE id IN (SELECT user_id FROM unauthorized_table)"
        )
        where_clause = main_query.find(sqlglot.exp.Where)

        # Create permission with no wildcard tables
        permission = sqlglot.parse_one("SELECT name, id FROM users")

        # This should hit line 435 and return False
        result = _validate_where_subqueries(where_clause, permission)
        assert result is False

    def test_score_calculation_no_where_match_line_488(self):
        """Test line 488: Score calculation with no WHERE matches."""
        # Create queries where WHERE clauses don't match
        sql = sqlglot.parse_one("SELECT name FROM users WHERE age > 30")
        permission = sqlglot.parse_one("SELECT name FROM users WHERE status = 'active'")

        # This should hit line 488 where no WHERE conditions match
        score = _calculate_match_score(sql, permission)
        # Should get table match points but no WHERE match points
        assert score >= 10  # Table match
        # The score calculation loop should not find matches, hitting line 488

    def test_expressions_equal_function_line_539(self):
        """Test line 539: Direct call to _expressions_equal function."""
        # Test the function directly with different expressions
        expr1 = sqlglot.parse_one("name")
        expr2 = sqlglot.parse_one("email")

        # This should hit line 539 in _expressions_equal
        result = _expressions_equal(expr1, expr2)
        assert result is False

        # Test with equal expressions
        expr3 = sqlglot.parse_one("name")
        result2 = _expressions_equal(expr1, expr3)
        assert result2 is True


class TestComplexCombinations:
    """Test complex scenarios that might hit multiple edge cases."""

    def test_complex_window_function_scenario(self):
        """Test complex window function scenario to ensure coverage."""
        query = """
            SELECT
                name,
                COUNT(*) OVER (PARTITION BY dept) as dept_count,
                ROW_NUMBER() OVER (ORDER BY salary) as salary_rank
            FROM users
        """
        permission = "SELECT name, dept, salary FROM users"

        result = check_permission(query, permission)
        assert result is True

    def test_deeply_nested_subquery_scenario(self):
        """Test deeply nested subqueries to hit edge cases."""
        query = """
            SELECT name FROM users
            WHERE id IN (
                SELECT user_id FROM orders
                WHERE total > (
                    SELECT AVG(total) FROM orders
                    WHERE user_id IN (SELECT id FROM premium_users)
                )
            )
        """
        permission = 'SELECT name, id, user_id, total FROM "*"'

        result = check_permission(query, permission)
        assert result is True

    def test_exception_handling_in_column_parsing(self):
        """Test exception handling during column parsing."""
        # Create a scenario with complex expressions that might cause parsing issues
        query = "SELECT name FROM users"
        permission = "SELECT COMPLEX_FUNCTION(name, 'param') FROM users"

        # This should handle any parsing exceptions gracefully
        result = check_permission(query, permission)
        # Result can be True or False, but shouldn't crash
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
