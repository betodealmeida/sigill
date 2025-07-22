"""
Tests for the improved tighten function that doesn't add NULL columns.
"""

import pytest
import sqlglot
from sigill import tighten


class TestTightenNoNull:
    """Test that tighten function no longer adds NULL columns."""

    def test_original_issue_fixed(self):
        """Test the original issue: SELECT name should not get extra NULL columns."""
        result = tighten(
            sql="SELECT name FROM users WHERE age > 18",
            permissions={"SELECT ANONYMIZE(name), age FROM users WHERE age > 21"},
        )
        
        # Should only include ANONYMIZE(name), no NULL for age
        assert result.sql() == "SELECT ANONYMIZE(name) FROM users WHERE age > 21"
        assert "NULL" not in result.sql()

    def test_multiple_matching_columns(self):
        """Test with multiple columns that match."""
        result = tighten(
            sql="SELECT name, age FROM users WHERE age > 18",
            permissions={"SELECT ANONYMIZE(name), age, salary FROM users WHERE age > 21"},
        )
        
        # Should include both matching columns, no NULL for salary
        expected = "SELECT ANONYMIZE(name), age FROM users WHERE age > 21"
        assert result.sql() == expected
        assert "NULL" not in result.sql()

    def test_exact_match(self):
        """Test when SQL and permission match exactly."""
        result = tighten(
            sql="SELECT name FROM users WHERE age > 21",
            permissions={"SELECT ANONYMIZE(name) FROM users WHERE age > 21"},
        )
        
        # Should be identical to permission
        assert result.sql() == "SELECT ANONYMIZE(name) FROM users WHERE age > 21"

    def test_partial_match_with_complex_expressions(self):
        """Test with complex expressions where some match."""
        result = tighten(
            sql="SELECT COUNT(*), name FROM users",
            permissions={"SELECT COUNT(*), ANONYMIZE(name), MAX(salary) FROM users"},
        )
        
        # Should include COUNT(*) and ANONYMIZE(name), skip MAX(salary)
        expected = "SELECT COUNT(*), ANONYMIZE(name) FROM users"
        assert result.sql() == expected
        assert "NULL" not in result.sql()

    def test_no_matching_columns_raises_error(self):
        """Test that no matching columns raises a helpful error."""
        with pytest.raises(ValueError, match="No matching projections found"):
            tighten(
                sql="SELECT email FROM users WHERE age > 18",
                permissions={"SELECT ANONYMIZE(name) FROM users WHERE age > 21"},
            )

    def test_anonymize_function_matching(self):
        """Test ANONYMIZE function matching works correctly."""
        result = tighten(
            sql="SELECT name, age FROM users",
            permissions={"SELECT ANONYMIZE(name), ANONYMIZE(email) FROM users"},
        )
        
        # Should only include ANONYMIZE(name), no ANONYMIZE(email) since email not in SQL
        expected = "SELECT ANONYMIZE(name) FROM users"
        assert result.sql() == expected
        assert "NULL" not in result.sql()

    def test_wildcard_permissions_still_work(self):
        """Test that wildcard permissions still work correctly."""
        result = tighten(
            sql="SELECT name FROM users WHERE age > 18",
            permissions={"SELECT * FROM users WHERE age > 21"},
        )
        
        # Should keep the original projection since * allows everything
        expected = "SELECT name FROM users WHERE age > 21"
        assert result.sql() == expected

    def test_complex_where_conditions_preserved(self):
        """Test that complex WHERE conditions are properly preserved."""
        result = tighten(
            sql="SELECT name, age FROM users WHERE department = 'eng'",
            permissions={"SELECT ANONYMIZE(name), age FROM users WHERE department = 'eng' AND salary > 50000"},
        )
        
        # Should include both matching columns with tighter WHERE
        expected = "SELECT ANONYMIZE(name), age FROM users WHERE department = 'eng' AND salary > 50000"
        assert result.sql() == expected
        assert "NULL" not in result.sql()


class TestTightenCompatibility:
    """Test that tighten function maintains backward compatibility for valid cases."""

    def test_original_functionality_preserved(self):
        """Test that the core tighten functionality still works."""
        # This used to work and should continue to work
        result = tighten(
            sql="SELECT a, b FROM users WHERE salary < 2000",
            permissions={"SELECT a, ANONYMIZE(b) FROM users WHERE id = 1 AND salary < 1000"},
        )
        
        # Should apply the permission constraints
        expected = "SELECT a, ANONYMIZE(b) FROM users WHERE id = 1 AND salary < 1000"
        assert result.sql() == expected

    def test_multiple_permissions_still_work(self):
        """Test that multiple permissions still work correctly."""
        permissions = {
            "SELECT name FROM users WHERE age > 25",
            "SELECT ANONYMIZE(name), age FROM users WHERE age > 18",
        }
        
        result = tighten(
            sql="SELECT name FROM users WHERE age > 20",
            permissions=permissions,
        )
        
        # Should pick the best matching permission
        sql_result = result.sql()
        assert "ANONYMIZE(name)" in sql_result or ("name" in sql_result and "ANONYMIZE" not in sql_result)
        assert "NULL" not in sql_result

    def test_from_clauses_copied_correctly(self):
        """Test that FROM, WHERE, GROUP BY clauses are copied correctly."""
        result = tighten(
            sql="SELECT name FROM users WHERE age > 18",
            permissions={"SELECT ANONYMIZE(name) FROM users WHERE age > 21 GROUP BY department"},
        )
        
        expected = "SELECT ANONYMIZE(name) FROM users WHERE age > 21 GROUP BY department"
        assert result.sql() == expected