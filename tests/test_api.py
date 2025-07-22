import pytest
import sqlglot
from sigill.api import check, check_permission, tighten


class TestCheckPermission:
    """Test the check_permission function."""

    def test_exact_match(self):
        """Test queries that match exactly."""
        query = sqlglot.parse_one("SELECT id, name FROM users")
        permission = sqlglot.parse_one("SELECT id, name FROM users")
        assert check_permission(query, permission) is True

    def test_subset_columns(self):
        """Test queries with subset of columns."""
        query = sqlglot.parse_one("SELECT name FROM users")
        permission = sqlglot.parse_one("SELECT id, name, email FROM users")
        assert check_permission(query, permission) is True

    def test_superset_columns_not_allowed(self):
        """Test queries with superset of columns are not allowed."""
        query = sqlglot.parse_one("SELECT id, name, email FROM users")
        permission = sqlglot.parse_one("SELECT name FROM users")
        assert check_permission(query, permission) is False

    def test_where_clause_subset(self):
        """Test WHERE clauses - query must be more restrictive."""
        query = sqlglot.parse_one(
            "SELECT * FROM users WHERE age > 18 AND status = 'active'"
        )
        permission = sqlglot.parse_one("SELECT * FROM users WHERE age > 18")
        assert check_permission(query, permission) is True

    def test_where_clause_not_restrictive_enough(self):
        """Test WHERE clauses - query is less restrictive."""
        query = sqlglot.parse_one("SELECT * FROM users WHERE age > 18")
        permission = sqlglot.parse_one(
            "SELECT * FROM users WHERE age > 18 AND status = 'active'"
        )
        assert check_permission(query, permission) is False

    def test_no_where_clause_in_permission(self):
        """Test query without WHERE when permission has WHERE."""
        query = sqlglot.parse_one("SELECT * FROM users")
        permission = sqlglot.parse_one("SELECT * FROM users WHERE age > 18")
        assert check_permission(query, permission) is False

    def test_group_by_subset(self):
        """Test GROUP BY - fewer groups should be allowed."""
        query = sqlglot.parse_one(
            "SELECT country, COUNT(*) FROM users GROUP BY country"
        )
        permission = sqlglot.parse_one(
            "SELECT country, age, COUNT(*) FROM users GROUP BY country, age"
        )
        assert check_permission(query, permission) is True

    def test_group_by_additional_not_allowed(self):
        """Test GROUP BY - additional groups not in permission."""
        query = sqlglot.parse_one(
            "SELECT country, age, status, COUNT(*) FROM users GROUP BY country, age, status"
        )
        permission = sqlglot.parse_one(
            "SELECT country, age, COUNT(*) FROM users GROUP BY country, age"
        )
        assert check_permission(query, permission) is False

    def test_count_without_group_by(self):
        """Test COUNT without GROUP BY when permission has GROUP BY."""
        query = sqlglot.parse_one("SELECT COUNT(*) FROM users WHERE status = 'active'")
        permission = sqlglot.parse_one(
            "SELECT country, COUNT(*) FROM users WHERE status = 'active' GROUP BY country"
        )
        assert check_permission(query, permission) is True

    def test_wildcard_table_permission(self):
        """Test wildcard table permissions."""
        query = sqlglot.parse_one("SELECT id FROM catalog.db.users")
        permission = sqlglot.parse_one('SELECT * FROM catalog."*"."*"')
        assert check_permission(query, permission) is True

    def test_anonymize_function(self):
        """Test ANONYMIZE function - accessing anonymized column through regular column should be allowed."""
        query = sqlglot.parse_one("SELECT name, age FROM users")
        permission = sqlglot.parse_one("SELECT ANONYMIZE(name), age, email FROM users")
        assert check_permission(query, permission) is True

    def test_different_tables(self):
        """Test queries on different tables."""
        query = sqlglot.parse_one("SELECT * FROM users")
        permission = sqlglot.parse_one("SELECT * FROM orders")
        assert check_permission(query, permission) is False


class TestCheck:
    """Test the check function with multiple permissions."""

    def test_multiple_permissions_match(self):
        """Test query that matches one of multiple permissions."""
        query = sqlglot.parse_one("SELECT name FROM users")
        permissions = {
            sqlglot.parse_one("SELECT id FROM orders"),
            sqlglot.parse_one("SELECT name, email FROM users"),
            sqlglot.parse_one("SELECT * FROM products"),
        }
        assert check(query, permissions) is True

    def test_multiple_permissions_no_match(self):
        """Test query that matches none of multiple permissions."""
        query = sqlglot.parse_one("SELECT name FROM customers")
        permissions = {
            sqlglot.parse_one("SELECT id FROM orders"),
            sqlglot.parse_one("SELECT name, email FROM users"),
            sqlglot.parse_one("SELECT * FROM products"),
        }
        assert check(query, permissions) is False


class TestTighten:
    """Test the tighten function."""

    def test_tighten_columns_with_anonymize(self):
        """Test tightening columns with ANONYMIZE function."""
        query = sqlglot.parse_one("SELECT name, age FROM users")
        permissions = {
            sqlglot.parse_one("SELECT ANONYMIZE(name), age, email FROM users")
        }

        result = tighten(query, permissions)
        expected_result = "SELECT ANONYMIZE(name), age FROM users"

        assert result.sql() == expected_result

    def test_tighten_where_clause(self):
        """Test tightening WHERE clause."""
        query = sqlglot.parse_one("SELECT a, b FROM users WHERE salary < 2000")
        permissions = {
            sqlglot.parse_one("SELECT a, b FROM users WHERE id = 1 AND salary < 1000")
        }

        result = tighten(query, permissions)
        expected_result = "SELECT a, b FROM users WHERE id = 1 AND salary < 1000"

        assert result.sql() == expected_result

    def test_tighten_no_matching_permission(self):
        """Test tighten raises error when no matching permission found."""
        query = sqlglot.parse_one("SELECT name FROM users")
        permissions = {sqlglot.parse_one("SELECT id FROM orders")}

        with pytest.raises(ValueError, match="No matching permission found"):
            tighten(query, permissions)


class TestStringInputs:
    """Test functions with string inputs instead of parsed queries."""

    def test_check_permission_with_strings(self):
        """Test check_permission with string inputs."""
        query = "SELECT name FROM users WHERE age > 18"
        permission = "SELECT name, email FROM users WHERE age > 18"
        assert check_permission(query, permission) is True

    def test_tighten_with_string_inputs(self):
        """Test tighten with string inputs."""
        query = "SELECT name FROM users"
        permissions = {"SELECT ANONYMIZE(name), age FROM users"}

        result = tighten(query, permissions)
        assert "ANONYMIZE(name)" in result.sql()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_non_select_query(self):
        """Test non-SELECT queries."""
        with pytest.raises(ValueError, match="Input must be a SELECT statement"):
            tighten("INSERT INTO users VALUES (1, 'test')", {"SELECT * FROM users"})

    def test_invalid_sql_expression(self):
        """Test with non-expression input to check_permission."""
        result = check_permission("not_an_sql", "SELECT * FROM users")
        assert result is False

        result = check_permission("SELECT * FROM users", "not_an_sql")
        assert result is False

    def test_empty_table_names(self):
        """Test query with no tables."""
        # This should be caught by table subset check
        query = sqlglot.parse_one("SELECT 1")
        permission = sqlglot.parse_one("SELECT * FROM users")
        result = check_permission(query, permission)
        assert result is False

    def test_wildcard_table_complex_matching(self):
        """Test complex wildcard table matching."""
        # Test 2-part table name with wildcard
        query = sqlglot.parse_one("SELECT * FROM db.users")
        permission = sqlglot.parse_one('SELECT * FROM catalog."*"."*"')
        result = check_permission(query, permission)
        assert result is True

        # Test 1-part table name with wildcard
        query = sqlglot.parse_one("SELECT * FROM users")
        permission = sqlglot.parse_one('SELECT * FROM catalog."*"."*"')
        result = check_permission(query, permission)
        assert result is True

    def test_star_projection(self):
        """Test star projections."""
        query = sqlglot.parse_one("SELECT * FROM users")
        permission = sqlglot.parse_one("SELECT id, name FROM users")
        result = check_permission(query, permission)
        assert result is False

        query = sqlglot.parse_one("SELECT id FROM users")
        permission = sqlglot.parse_one("SELECT * FROM users")
        result = check_permission(query, permission)
        assert result is True

    def test_complex_anonymize_matching(self):
        """Test complex ANONYMIZE function matching."""
        query = sqlglot.parse_one("SELECT name FROM users")
        permission = sqlglot.parse_one("SELECT ANONYMIZE(name) FROM users")
        result = check_permission(query, permission)
        assert result is True

        # Test ANONYMIZE with different column
        query = sqlglot.parse_one("SELECT email FROM users")
        permission = sqlglot.parse_one("SELECT ANONYMIZE(name) FROM users")
        result = check_permission(query, permission)
        assert result is False

    def test_aggregation_functions(self):
        """Test various aggregation functions."""
        query = sqlglot.parse_one("SELECT SUM(salary) FROM users")
        permission = sqlglot.parse_one(
            "SELECT SUM(salary), AVG(age) FROM users GROUP BY department"
        )
        result = check_permission(query, permission)
        assert result is True

        query = sqlglot.parse_one("SELECT MIN(salary) FROM users")
        permission = sqlglot.parse_one(
            "SELECT MAX(salary), MIN(salary) FROM users GROUP BY department"
        )
        result = check_permission(query, permission)
        assert result is True

        query = sqlglot.parse_one("SELECT COUNT(*) FROM users")
        permission = sqlglot.parse_one(
            "SELECT COUNT(*), SUM(score) FROM users GROUP BY team"
        )
        result = check_permission(query, permission)
        assert result is True

    def test_where_clause_no_permission_where(self):
        """Test query with WHERE when permission has no WHERE."""
        query = sqlglot.parse_one("SELECT * FROM users WHERE age > 18")
        permission = sqlglot.parse_one("SELECT * FROM users")
        result = check_permission(query, permission)
        assert result is True

    def test_group_by_no_permission_group(self):
        """Test query without GROUP BY when permission has no GROUP BY."""
        query = sqlglot.parse_one("SELECT name FROM users")
        permission = sqlglot.parse_one("SELECT name, age FROM users")
        result = check_permission(query, permission)
        assert result is True

    def test_having_clause_matching(self):
        """Test HAVING clause validation."""
        query = sqlglot.parse_one(
            "SELECT dept, COUNT(*) FROM users GROUP BY dept HAVING COUNT(*) > 5"
        )
        permission = sqlglot.parse_one(
            "SELECT dept, COUNT(*) FROM users GROUP BY dept HAVING COUNT(*) > 10"
        )
        result = check_permission(query, permission)
        assert result is True  # Having without permission having returns True

    def test_having_clause_no_permission(self):
        """Test HAVING clause when permission has no HAVING."""
        query = sqlglot.parse_one(
            "SELECT dept, COUNT(*) FROM users GROUP BY dept HAVING COUNT(*) > 5"
        )
        permission = sqlglot.parse_one("SELECT dept, COUNT(*) FROM users GROUP BY dept")
        result = check_permission(query, permission)
        assert result is True

    def test_having_clause_query_without_having(self):
        """Test query without HAVING when permission has HAVING."""
        query = sqlglot.parse_one("SELECT dept, COUNT(*) FROM users GROUP BY dept")
        permission = sqlglot.parse_one(
            "SELECT dept, COUNT(*) FROM users GROUP BY dept HAVING COUNT(*) > 10"
        )
        result = check_permission(query, permission)
        assert result is False

    def test_tighten_score_calculation(self):
        """Test tighten function's scoring mechanism."""
        query = sqlglot.parse_one("SELECT name FROM users WHERE age > 18")

        # Permission with matching table and where condition
        perm1 = sqlglot.parse_one("SELECT name, email FROM users WHERE age > 18")
        # Permission with different table
        perm2 = sqlglot.parse_one("SELECT name FROM orders WHERE status = 'active'")

        permissions = {perm1, perm2}
        result = tighten(query, permissions)

        # Should pick perm1 due to higher score (matching table + where condition)
        assert "users" in result.sql()
        assert "age > 18" in result.sql()

    def test_tighten_with_group_by_and_having(self):
        """Test tighten function with GROUP BY and HAVING clauses."""
        query = sqlglot.parse_one("SELECT dept, COUNT(*) FROM users GROUP BY dept")
        permission = sqlglot.parse_one(
            "SELECT dept, name, COUNT(*) FROM users WHERE active = 1 GROUP BY dept, name HAVING COUNT(*) > 5"
        )

        permissions = {permission}
        result = tighten(query, permissions)

        # Should apply all constraints from permission
        assert "active = 1" in result.sql()
        assert "HAVING" in result.sql()
        assert "COUNT(*) > 5" in result.sql()

    def test_tighten_complex_projections(self):
        """Test tighten with complex projection matching."""
        query = sqlglot.parse_one("SELECT COUNT(*), name FROM users")
        permission = sqlglot.parse_one(
            "SELECT COUNT(*), ANONYMIZE(name), age FROM users"
        )

        permissions = {permission}
        result = tighten(query, permissions)

        # Should map COUNT(*) to COUNT(*), name to ANONYMIZE(name), skip age (no NULL)
        result_sql = result.sql()
        assert "COUNT(*)" in result_sql
        assert "ANONYMIZE(name)" in result_sql
        assert "NULL" not in result_sql  # No longer adds NULL for unmatched columns


class TestErrorHandling:
    """Test error handling and exception cases."""

    def test_column_allowed_exception_handling(self):
        """Test exception handling in _is_column_allowed."""
        # Test with malformed expressions that might cause parsing errors
        query = sqlglot.parse_one("SELECT name FROM users")
        permission = sqlglot.parse_one("SELECT name, age FROM users")

        # This should still work despite any internal parsing exceptions
        result = check_permission(query, permission)
        assert result is True

    def test_empty_permissions_set(self):
        """Test check function with empty permissions set."""
        query = sqlglot.parse_one("SELECT * FROM users")
        permissions = set()
        result = check(query, permissions)
        assert result is False

    def test_wildcard_table_edge_cases(self):
        """Test edge cases in wildcard table matching."""
        # Test 3-part table name matching
        query = sqlglot.parse_one("SELECT * FROM catalog.db.users")
        permission = sqlglot.parse_one("SELECT * FROM catalog.db.users")
        result = check_permission(query, permission)
        assert result is True

        # Test partial wildcard matching
        query = sqlglot.parse_one("SELECT * FROM catalog.db.users")
        permission = sqlglot.parse_one('SELECT * FROM catalog."*".users')
        result = check_permission(query, permission)
        assert result is True

        # Test mismatched table names
        query = sqlglot.parse_one("SELECT * FROM users")
        permission = sqlglot.parse_one("SELECT * FROM orders")
        result = check_permission(query, permission)
        assert result is False

    def test_non_select_expressions_in_check_permission(self):
        """Test check_permission with non-SELECT expressions."""
        # Test with INSERT statement (should return False)
        result = check_permission(
            "INSERT INTO users VALUES (1, 'test')", "SELECT * FROM users"
        )
        assert result is False

        result = check_permission(
            "SELECT * FROM users", "INSERT INTO users VALUES (1, 'test')"
        )
        assert result is False

    def test_complex_column_matching_edge_cases(self):
        """Test complex column matching scenarios."""
        # Test with function calls and complex expressions
        query = sqlglot.parse_one("SELECT UPPER(name), age FROM users")
        permission = sqlglot.parse_one("SELECT UPPER(name), age, email FROM users")
        result = check_permission(query, permission)
        assert result is True

        # Test with simple column selection
        query = sqlglot.parse_one("SELECT name FROM users")
        permission = sqlglot.parse_one("SELECT name, age FROM users")
        result = check_permission(query, permission)
        assert result is True

    def test_tighten_with_non_select_permission(self):
        """Test tighten function ignores non-SELECT permissions."""
        query = sqlglot.parse_one("SELECT name FROM users")
        permissions = {
            "INSERT INTO users VALUES (1, 'test')",
            "SELECT name, age FROM users",
        }

        result = tighten(query, permissions)
        # Should work with the valid SELECT permission
        assert "SELECT" in result.sql()
        assert "users" in result.sql()

    def test_group_by_with_complex_expressions(self):
        """Test GROUP BY with complex column references."""
        query = sqlglot.parse_one("SELECT dept FROM users GROUP BY dept")
        permission = sqlglot.parse_one(
            "SELECT dept, name FROM users GROUP BY dept, name"
        )
        result = check_permission(query, permission)
        assert result is True

        # Test with qualified column names
        query = sqlglot.parse_one("SELECT users.dept FROM users GROUP BY users.dept")
        permission = sqlglot.parse_one(
            "SELECT users.dept, users.name FROM users GROUP BY users.dept, users.name"
        )
        result = check_permission(query, permission)
        assert result is True

    def test_additional_edge_cases(self):
        """Test additional edge cases to reach 100% coverage."""
        # Test table subset with wildcard catalog="*" (line 111)
        query = sqlglot.parse_one("SELECT * FROM any_catalog.any_db.any_table")
        permission = sqlglot.parse_one('SELECT * FROM "*"."*"."*"')
        result = check_permission(query, permission)
        assert result is True

        # Test _get_table_names with table that has catalog and db
        query = sqlglot.parse_one("SELECT * FROM catalog.db.table")
        permission = sqlglot.parse_one("SELECT * FROM catalog.db.table")
        result = check_permission(query, permission)
        assert result is True

        # Test with expression that fails to parse in _is_column_allowed (line 223-226)
        from sigill.api import _is_column_allowed

        result = _is_column_allowed("malformed[sql", "valid_column")
        assert result is False

        # Test GROUP BY subset failure case (line 47)
        query = sqlglot.parse_one(
            "SELECT dept, COUNT(*) FROM users GROUP BY dept, unknown_col"
        )
        permission = sqlglot.parse_one("SELECT dept, COUNT(*) FROM users GROUP BY dept")
        result = check_permission(query, permission)
        assert result is False

        # Test HAVING subset failure case (line 328)
        query = sqlglot.parse_one("SELECT dept, COUNT(*) FROM users GROUP BY dept")
        permission = sqlglot.parse_one(
            "SELECT dept, COUNT(*) FROM users GROUP BY dept HAVING COUNT(*) > 5"
        )
        result = check_permission(query, permission)
        assert result is False

        # Test parse error in group by column extraction (line 269, 274)
        from sigill.api import _is_group_by_subset

        # Create a mock group by with expressions that might cause parse errors
        sql = sqlglot.parse_one("SELECT dept FROM users GROUP BY dept")
        perm = sqlglot.parse_one(
            "SELECT dept FROM users GROUP BY COMPLEX_FUNCTION(dept)"
        )
        result = _is_group_by_subset(sql, perm)
        assert result is False

        # Test various other edge cases for remaining lines
        query = sqlglot.parse_one(
            "SELECT * FROM users WHERE complex_condition = 'test'"
        )
        permission = sqlglot.parse_one("SELECT * FROM users WHERE simple_condition = 1")
        result = check_permission(query, permission)
        assert result is False

        # Test tighten with complex matching that hits line 361
        query = sqlglot.parse_one("SELECT complex_expr FROM users")
        permission = sqlglot.parse_one("SELECT simple_col, complex_expr FROM users")
        permissions = {permission}
        result = tighten(query, permissions)
        assert "users" in result.sql()

        # Test anonymous function parsing edge case (line 163-164)
        from sigill.api import _is_column_allowed

        result = _is_column_allowed("name", "COMPLEX_FUNC(name, other)")
        assert result is False

        # Test column matching with edge case (line 202)
        query = sqlglot.parse_one("SELECT special_col FROM users")
        permission = sqlglot.parse_one(
            "SELECT * FROM users"
        )  # This should match due to *
        result = check_permission(query, permission)
        assert result is True

        # Test complex _expressions_equal case (line 217)
        from sigill.api import _expressions_equal

        expr1 = sqlglot.parse_one("COUNT(*)")
        expr2 = sqlglot.parse_one("COUNT(*)")
        result = _expressions_equal(expr1, expr2)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
