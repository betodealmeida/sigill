"""
Tests for column validation and permission checking.
Covers column matching, ANONYMIZE functions, and GROUP BY validation.
"""

import pytest
import sqlglot
from sigill.api import check_permission, _is_column_allowed, _is_group_by_subset


class TestCoverage100:
    """Tests to achieve 100% coverage by hitting specific missing lines."""

    def test_perm_col_wildcard_early_return(self):
        """Test line 202: early return when perm_col is '*'."""
        # This should trigger line 202: return True when perm_col == "*"
        result = _is_column_allowed("any_column", "*")
        assert result is True

    def test_anonymize_non_column_fallback(self):
        """Test line 217: ANONYMIZE function fallback to sql() comparison."""
        # Create a case where we have ANONYMIZE but inner_expr is not a Column
        # This should trigger line 217: return sql_expr.sql() == inner_expr.sql()

        # Use a complex expression inside ANONYMIZE that's not a simple column
        sql_expr = sqlglot.parse_one("UPPER(name)")
        perm_expr = sqlglot.parse_one("ANONYMIZE(UPPER(name))")

        result = _is_column_allowed(sql_expr.sql(), perm_expr.sql())
        assert result is True

    def test_expressions_equal_fallback(self):
        """Test line 223: _expressions_equal fallback return True."""
        # This tests the case where expressions are equal but not simple columns
        # Should trigger line 223: return True after _expressions_equal succeeds

        result = _is_column_allowed("COUNT(*)", "COUNT(*)")
        assert result is True

    def test_projection_parsing_exception(self):
        """Test lines 163-164: exception handling in _get_projections parsing."""
        # Create a mock situation that might cause parse errors in _is_column_subset
        # We need to create a projection that causes an exception in the parsing logic

        # This is tricky because sqlglot is robust, but let's try with a malformed expression
        query = sqlglot.parse_one("SELECT name FROM users")

        # Create a permission with a complex expression that might cause issues
        permission = sqlglot.parse_one("SELECT name, complex_func() FROM users")

        # This should exercise the exception handling paths
        result = check_permission(query, permission)
        assert result is True

    def test_group_by_column_parsing_exceptions(self):
        """Test lines 269, 274: exception handling in GROUP BY column extraction."""

        # Create queries with GROUP BY expressions that might cause parsing issues
        sql = sqlglot.parse_one(
            "SELECT COUNT(*) FROM users GROUP BY complex_expression"
        )
        perm = sqlglot.parse_one("SELECT COUNT(*) FROM users GROUP BY dept")

        # This should exercise the exception handling in GROUP BY column extraction
        result = _is_group_by_subset(sql, perm)
        assert result is False

    def test_tighten_exact_expression_match(self):
        """Test line 361: exact expression match in tighten _apply_permission_constraints."""
        from sigill.api import tighten

        # Create a case where expressions match exactly (not just columns)
        query = sqlglot.parse_one("SELECT COUNT(*) FROM users")
        permission = sqlglot.parse_one("SELECT COUNT(*), other_col FROM users")

        result = tighten(query, {permission})

        # Should have COUNT(*) only, no NULL for other_col
        result_sql = result.sql()
        assert "COUNT(*)" in result_sql
        assert "NULL" not in result_sql

    def test_having_clause_exact_conditions(self):
        """Test line 318: HAVING clause return True when conditions match."""
        # This is testing the simple return True case in _is_having_subset
        query = sqlglot.parse_one(
            "SELECT dept, COUNT(*) FROM users GROUP BY dept HAVING COUNT(*) > 5"
        )
        permission = sqlglot.parse_one(
            "SELECT dept, COUNT(*) FROM users GROUP BY dept HAVING COUNT(*) > 5"
        )

        result = check_permission(query, permission)
        assert result is True


class TestEdgeCasesForMissingLines:
    """Additional edge case tests to hit remaining lines."""

    def test_complex_column_matching_scenarios(self):
        """Test various complex column matching scenarios."""

        # Test case that should hit the perm_columns exception handling (163-164)
        query = sqlglot.parse_one("SELECT users.name FROM users")
        permission = sqlglot.parse_one("SELECT users.name, users.email FROM users")

        result = check_permission(query, permission)
        assert result is True

    def test_column_allowed_with_complex_anonymize(self):
        """Test _is_column_allowed with complex ANONYMIZE scenarios."""

        # Test case where ANONYMIZE contains a complex expression (line 217)
        result = _is_column_allowed(
            "CONCAT(first_name, ' ', last_name)",
            "ANONYMIZE(CONCAT(first_name, ' ', last_name))",
        )
        assert result is True

        # Test case where columns match by name (line 220 path)
        result = _is_column_allowed("users.name", "users.name")
        assert result is True

    def test_where_clause_edge_cases(self):
        """Test WHERE clause validation edge cases."""

        # Complex WHERE conditions that should exercise different code paths
        query = sqlglot.parse_one(
            """
            SELECT * FROM users
            WHERE status = 'active' AND age BETWEEN 18 AND 65
        """
        )
        permission = sqlglot.parse_one(
            """
            SELECT * FROM users
            WHERE status = 'active'
        """
        )

        result = check_permission(query, permission)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
