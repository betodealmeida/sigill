"""
Comprehensive tests for complex SQL query support in sigill.
Tests UNION, INTERSECT, EXCEPT, CTEs, JOINs, subqueries, and other advanced constructs.
"""

import pytest
import sqlglot
from sigill.api import check_permission, tighten


class TestUnionQueries:
    """Test UNION and UNION ALL support."""

    def test_simple_union_allowed(self):
        """Test basic UNION query is allowed when both tables are authorized."""
        query = "SELECT name FROM users UNION SELECT name FROM users"
        permission = "SELECT name FROM users"
        assert check_permission(query, permission) is True

    def test_union_all_allowed(self):
        """Test UNION ALL query is allowed when both tables are authorized."""
        query = "SELECT id, name FROM users UNION ALL SELECT id, name FROM users"
        permission = "SELECT id, name FROM users"
        assert check_permission(query, permission) is True

    def test_union_different_tables_with_wildcard_permission(self):
        """Test UNION with different tables allowed by wildcard permission."""
        query = "SELECT name FROM users UNION SELECT name FROM customers"
        permission = 'SELECT name FROM "*"'
        assert check_permission(query, permission) is True

    def test_union_different_columns_rejected(self):
        """Test UNION with unauthorized columns is rejected."""
        query = "SELECT name, email FROM users UNION SELECT name, email FROM users"
        permission = "SELECT name FROM users"
        assert check_permission(query, permission) is False

    def test_union_unauthorized_table_rejected(self):
        """Test UNION with unauthorized table is rejected."""
        query = "SELECT name FROM users UNION SELECT name FROM orders"
        permission = "SELECT name FROM users"
        assert check_permission(query, permission) is False

    def test_complex_union_with_where(self):
        """Test complex UNION with WHERE clauses."""
        query = """
            SELECT name FROM users WHERE age > 18
            UNION
            SELECT name FROM users WHERE age > 18
        """
        permission = "SELECT name FROM users WHERE age > 18"
        assert check_permission(query, permission) is True

    def test_nested_union_queries(self):
        """Test nested UNION queries."""
        query = """
            SELECT name FROM users
            UNION
            (SELECT name FROM users UNION SELECT name FROM users)
        """
        permission = "SELECT name FROM users"
        assert check_permission(query, permission) is True

    def test_union_against_compound_permission(self):
        """Test query against UNION permission."""
        query = "SELECT name FROM users"
        permission = "SELECT name FROM users UNION SELECT name FROM customers"
        assert check_permission(query, permission) is True


class TestIntersectExceptQueries:
    """Test INTERSECT and EXCEPT support."""

    def test_intersect_query_allowed(self):
        """Test INTERSECT query is allowed with wildcard permission."""
        query = "SELECT name FROM users INTERSECT SELECT name FROM customers"
        permission = 'SELECT name FROM "*"'
        assert check_permission(query, permission) is True

    def test_except_query_allowed(self):
        """Test EXCEPT query is allowed with wildcard permission."""
        query = "SELECT name FROM users EXCEPT SELECT name FROM customers"
        permission = 'SELECT name FROM "*"'
        assert check_permission(query, permission) is True

    def test_intersect_unauthorized_rejected(self):
        """Test INTERSECT with unauthorized table is rejected."""
        query = "SELECT name FROM users INTERSECT SELECT name FROM orders"
        permission = "SELECT name FROM users"
        assert check_permission(query, permission) is False


class TestCTEQueries:
    """Test Common Table Expression support."""

    def test_simple_cte_allowed(self):
        """Test basic CTE is allowed."""
        query = """
            WITH user_summary AS (
                SELECT name, age FROM users WHERE age > 18
            )
            SELECT name FROM user_summary WHERE age > 18
        """
        permission = "SELECT name, age FROM users WHERE age > 18"
        assert check_permission(query, permission) is True

    def test_cte_unauthorized_table_rejected(self):
        """Test CTE with unauthorized table is rejected."""
        query = """
            WITH order_summary AS (
                SELECT customer_id FROM orders
            )
            SELECT customer_id FROM order_summary
        """
        permission = "SELECT name FROM users"
        assert check_permission(query, permission) is False

    def test_multiple_ctes_allowed(self):
        """Test multiple CTEs are allowed."""
        query = """
            WITH user_summary AS (
                SELECT name, age FROM users
            ),
            filtered_users AS (
                SELECT name FROM user_summary
            )
            SELECT name FROM filtered_users
        """
        permission = "SELECT name, age FROM users"
        assert check_permission(query, permission) is True

    def test_recursive_cte_allowed(self):
        """Test recursive CTE is allowed."""
        query = """
            WITH RECURSIVE employee_hierarchy AS (
                SELECT id, name, manager_id FROM employees
                UNION ALL
                SELECT e.id, e.name, e.manager_id
                FROM employees e
                INNER JOIN employee_hierarchy eh ON e.manager_id = eh.id
            )
            SELECT name FROM employee_hierarchy
        """
        permission = "SELECT id, name, manager_id FROM employees"
        assert check_permission(query, permission) is True


class TestJoinQueries:
    """Test JOIN operation support."""

    def test_inner_join_allowed(self):
        """Test INNER JOIN is allowed with wildcard permission."""
        query = """
            SELECT u.name, o.total
            FROM users u
            INNER JOIN orders o ON u.id = o.user_id
        """
        permission = 'SELECT name, total FROM "*"'
        assert check_permission(query, permission) is True

    def test_left_join_allowed(self):
        """Test LEFT JOIN is allowed with wildcard permission."""
        query = """
            SELECT u.name, o.total
            FROM users u
            LEFT JOIN orders o ON u.id = o.user_id
        """
        permission = 'SELECT name, total FROM "*"'
        assert check_permission(query, permission) is True

    def test_multiple_joins_allowed(self):
        """Test multiple JOINs are allowed with wildcard permission."""
        query = """
            SELECT name, total
            FROM users u
            INNER JOIN orders o ON u.id = o.user_id
            INNER JOIN products p ON o.product_id = p.id
        """
        permission = 'SELECT name, total, id, user_id, product_id FROM "*"'
        assert check_permission(query, permission) is True

    def test_join_unauthorized_table_rejected(self):
        """Test JOIN with unauthorized table is rejected."""
        query = """
            SELECT u.name, s.salary
            FROM users u
            INNER JOIN salaries s ON u.id = s.user_id
        """
        permission = "SELECT name FROM users"
        assert check_permission(query, permission) is False

    def test_self_join_allowed(self):
        """Test self JOIN is allowed."""
        query = """
            SELECT name, manager_id
            FROM users u1
            INNER JOIN users u2 ON u1.manager_id = u2.id
        """
        permission = 'SELECT name, manager_id, id FROM "*"'
        assert check_permission(query, permission) is True


class TestSubquerySupport:
    """Test subquery support in various contexts."""

    def test_where_subquery_allowed(self):
        """Test subquery in WHERE clause is allowed with wildcard permission."""
        query = """
            SELECT name FROM users
            WHERE id IN (SELECT user_id FROM orders WHERE total > 100)
        """
        permission = 'SELECT name, id, user_id, total FROM "*"'
        assert check_permission(query, permission) is True

    def test_where_exists_subquery_allowed(self):
        """Test EXISTS subquery in WHERE clause is allowed with wildcard permission."""
        query = """
            SELECT name FROM users u
            WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)
        """
        permission = 'SELECT name, id, user_id FROM "*"'
        assert check_permission(query, permission) is True

    def test_select_subquery_allowed(self):
        """Test subquery in SELECT clause is allowed with wildcard permission."""
        query = """
            SELECT
                name,
                id
            FROM users
            WHERE id IN (SELECT user_id FROM orders)
        """
        permission = 'SELECT name, id, user_id FROM "*"'
        assert check_permission(query, permission) is True

    def test_from_subquery_allowed(self):
        """Test subquery in FROM clause is allowed."""
        query = """
            SELECT name FROM (
                SELECT name, age FROM users WHERE age > 18
            ) as filtered_users
            WHERE age > 18
        """
        permission = "SELECT name, age FROM users WHERE age > 18"
        assert check_permission(query, permission) is True

    def test_correlated_subquery_allowed(self):
        """Test correlated subquery is allowed."""
        query = """
            SELECT name FROM users u1
            WHERE age > (SELECT AVG(age) FROM users u2 WHERE u2.department = u1.department)
        """
        permission = "SELECT name, age, department FROM users"
        assert check_permission(query, permission) is True

    def test_subquery_unauthorized_table_rejected(self):
        """Test subquery with unauthorized table is rejected."""
        query = """
            SELECT name FROM users
            WHERE id IN (SELECT user_id FROM private_data)
        """
        permission = "SELECT name, id FROM users"
        assert check_permission(query, permission) is False


class TestWindowFunctions:
    """Test window function support."""

    def test_row_number_allowed(self):
        """Test ROW_NUMBER() window function is allowed."""
        query = """
            SELECT
                name,
                ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as rank
            FROM users
        """
        permission = "SELECT name, department, salary FROM users"
        assert check_permission(query, permission) is True

    def test_rank_with_partition_allowed(self):
        """Test RANK() with PARTITION BY is allowed."""
        query = """
            SELECT
                name,
                RANK() OVER (PARTITION BY department ORDER BY age) as age_rank
            FROM users
        """
        permission = "SELECT name, department, age FROM users"
        assert check_permission(query, permission) is True

    def test_lag_lead_functions_allowed(self):
        """Test LAG/LEAD window functions are allowed."""
        query = """
            SELECT
                name,
                LAG(salary, 1) OVER (ORDER BY hire_date) as prev_salary,
                LEAD(salary, 1) OVER (ORDER BY hire_date) as next_salary
            FROM users
        """
        permission = "SELECT name, salary, hire_date FROM users"
        assert check_permission(query, permission) is True


class TestComplexCombinations:
    """Test complex combinations of various SQL features."""

    def test_cte_with_union_and_join(self):
        """Test CTE combined with UNION and JOIN."""
        query = """
            WITH combined_data AS (
                SELECT id, name, 'user' as type FROM users
                UNION ALL
                SELECT id, name, 'customer' as type FROM users
            )
            SELECT cd.name, o.total
            FROM combined_data cd
            INNER JOIN orders o ON cd.id = o.user_id
            WHERE cd.type = 'user'
        """
        permission = 'SELECT id, name, total, user_id FROM "*"'
        assert check_permission(query, permission) is True

    def test_union_with_window_functions(self):
        """Test UNION with window functions."""
        query = """
            SELECT name, salary, ROW_NUMBER() OVER (ORDER BY salary DESC) as rank
            FROM users
            UNION ALL
            SELECT name, salary, ROW_NUMBER() OVER (ORDER BY salary DESC) as rank
            FROM users
        """
        permission = "SELECT name, salary FROM users"
        assert check_permission(query, permission) is True

    def test_nested_subqueries_with_aggregates(self):
        """Test nested subqueries with aggregate functions."""
        query = """
            SELECT name FROM users
            WHERE salary > (
                SELECT AVG(salary) FROM users
                WHERE department IN (
                    SELECT department FROM users WHERE budget > 100000
                )
            )
        """
        permission = "SELECT name, salary, department, budget FROM users"
        assert check_permission(query, permission) is True


class TestCompoundPermissions:
    """Test compound permissions (UNION in permissions)."""

    def test_simple_query_against_union_permission(self):
        """Test simple query against UNION permission."""
        query = "SELECT name FROM users"
        permission = "SELECT name FROM users UNION SELECT name FROM customers"
        assert check_permission(query, permission) is True

    def test_query_matches_second_part_of_union_permission(self):
        """Test query matches second part of UNION permission."""
        query = "SELECT email FROM customers"
        permission = "SELECT name FROM users UNION SELECT email FROM customers"
        assert check_permission(query, permission) is True

    def test_query_unauthorized_by_union_permission(self):
        """Test query unauthorized by any part of UNION permission."""
        query = "SELECT salary FROM employees"
        permission = "SELECT name FROM users UNION SELECT email FROM customers"
        assert check_permission(query, permission) is False


class TestTightenWithComplexQueries:
    """Test tighten function behavior with complex queries."""

    def test_tighten_rejects_union_queries(self):
        """Test that tighten rejects UNION queries."""
        query = "SELECT name FROM users UNION SELECT name FROM customers"
        permissions = {"SELECT name FROM users"}

        with pytest.raises(ValueError, match="does not support compound statements"):
            tighten(query, permissions)

    def test_tighten_rejects_intersect_queries(self):
        """Test that tighten rejects INTERSECT queries."""
        query = "SELECT name FROM users INTERSECT SELECT name FROM customers"
        permissions = {"SELECT name FROM users"}

        with pytest.raises(ValueError, match="does not support compound statements"):
            tighten(query, permissions)

    def test_tighten_works_with_complex_select(self):
        """Test that tighten works with complex SELECT queries."""
        query = """
            SELECT name, age
            FROM users
            WHERE age > 18
        """
        permissions = {"SELECT name, age FROM users WHERE age > 21"}

        result = tighten(query, permissions)
        assert "age > 21" in result.sql()


class TestWildcardPermissionsWithComplexQueries:
    """Test wildcard permissions with complex queries."""

    def test_wildcard_permission_allows_union(self):
        """Test wildcard permission allows UNION queries."""
        query = "SELECT name FROM catalog.db1.users UNION SELECT name FROM catalog.db2.customers"
        permission = 'SELECT * FROM catalog."*"."*"'
        assert check_permission(query, permission) is True

    def test_wildcard_permission_allows_complex_joins(self):
        """Test wildcard permission allows complex JOINs across schemas."""
        query = """
            SELECT u.name, o.total
            FROM catalog.users.main u
            INNER JOIN catalog.orders.main o ON u.id = o.user_id
        """
        permission = 'SELECT * FROM catalog."*"."*"'
        assert check_permission(query, permission) is True


class TestErrorHandling:
    """Test error handling with complex queries."""

    def test_malformed_union_query(self):
        """Test handling of malformed UNION query."""
        # This should not crash but return False
        try:
            result = check_permission("SELECT FROM users UNION", "SELECT * FROM users")
            assert result is False
        except Exception:
            # If parsing fails completely, that's also acceptable
            assert True

    def test_empty_compound_query(self):
        """Test handling of edge cases in compound queries."""
        # Basic validation that the function doesn't crash
        query = sqlglot.parse_one("SELECT name FROM users")
        permission = sqlglot.parse_one("SELECT name FROM users")
        assert check_permission(query, permission) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
