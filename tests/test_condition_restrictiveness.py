"""
Tests for WHERE condition restrictiveness logic.
Ensures that more restrictive conditions are properly recognized.
"""

from sigill.api import check_permission


class TestConditionRestrictiveness:
    """Test that WHERE conditions handle restrictiveness correctly."""

    def test_greater_than_more_restrictive(self):
        """Test that age > 21 is more restrictive than age > 18."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age > 21",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is True

    def test_greater_than_less_restrictive_rejected(self):
        """Test that age > 15 is less restrictive than age > 18."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age > 15",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is False

    def test_greater_equal_more_restrictive(self):
        """Test that age >= 21 is more restrictive than age >= 18."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age >= 21",
            permission="SELECT name FROM users WHERE age >= 18",
        )
        assert result is True

    def test_mixed_greater_operations(self):
        """Test mixing >= and > operations."""
        # age >= 22 is more restrictive than age > 21
        result = check_permission(
            sql="SELECT name FROM users WHERE age >= 22",
            permission="SELECT name FROM users WHERE age > 21",
        )
        assert result is True

        # age > 21 is more restrictive than age >= 21
        result = check_permission(
            sql="SELECT name FROM users WHERE age > 21",
            permission="SELECT name FROM users WHERE age >= 21",
        )
        assert result is True

    def test_less_than_more_restrictive(self):
        """Test that age < 18 is more restrictive than age < 21."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age < 18",
            permission="SELECT name FROM users WHERE age < 21",
        )
        assert result is True

    def test_less_than_less_restrictive_rejected(self):
        """Test that age < 25 is less restrictive than age < 21."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age < 25",
            permission="SELECT name FROM users WHERE age < 21",
        )
        assert result is False

    def test_equality_more_restrictive(self):
        """Test that equality conditions are more restrictive."""
        # age = 20 satisfies age > 18
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 20",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is True

        # age = 15 does not satisfy age > 18
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 15",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is False

    def test_exact_condition_match(self):
        """Test that exact condition matches still work."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age > 18",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is True

    def test_different_columns_rejected(self):
        """Test that conditions on different columns don't match."""
        result = check_permission(
            sql="SELECT name FROM users WHERE salary > 50000",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is False

    def test_non_numeric_conditions_fallback(self):
        """Test that non-numeric conditions fall back to exact matching."""
        result = check_permission(
            sql="SELECT name FROM users WHERE status = 'active'",
            permission="SELECT name FROM users WHERE status = 'active'",
        )
        assert result is True

        result = check_permission(
            sql="SELECT name FROM users WHERE status = 'inactive'",
            permission="SELECT name FROM users WHERE status = 'active'",
        )
        assert result is False


class TestComplexConditionScenarios:
    """Test complex scenarios with multiple conditions."""

    def test_multiple_and_conditions(self):
        """Test queries with multiple AND conditions."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age > 21 AND salary > 50000",
            permission="SELECT name FROM users WHERE age > 18 AND salary > 40000",
        )
        assert result is True

    def test_partial_condition_match_rejected(self):
        """Test that partial condition matches are rejected."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age > 21",
            permission="SELECT name FROM users WHERE age > 18 AND department = 'engineering'",
        )
        assert result is False  # Missing department condition

    def test_additional_restrictive_conditions_allowed(self):
        """Test that additional restrictive conditions are allowed."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age > 21 AND department = 'engineering'",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is True  # Additional condition makes it more restrictive

    def test_string_conditions_with_numbers(self):
        """Test string values that look like numbers."""
        result = check_permission(
            sql="SELECT name FROM products WHERE price > 100.50",
            permission="SELECT name FROM products WHERE price > 50.25",
        )
        assert result is True
