"""
Tests for numeric comparison logic in WHERE condition restrictiveness.
Covers edge cases for binary operations, numeric value extraction, and operator comparisons.
"""

import sqlglot
from sigill.api import (
    check_permission,
    _condition_satisfies_permission,
    _compare_binary_conditions,
    _extract_numeric_value,
    _is_more_restrictive,
)


class TestUncoveredLines:
    """Tests to cover specific lines that are missing coverage."""

    def test_line_513_condition_satisfies_permission_fallback(self):
        """Test line 513: return False when conditions aren't both binary."""
        sql_expr = sqlglot.parse_one("SELECT name FROM users WHERE age IN (1, 2, 3)")
        perm_expr = sqlglot.parse_one("SELECT name FROM users WHERE age > 18")

        sql_where = sql_expr.args.get("where")
        perm_where = perm_expr.args.get("where")

        # One condition is IN, other is >, should return False at line 513
        result = _condition_satisfies_permission(sql_where.this, perm_where.this)
        assert result is False

    def test_lines_537_538_compare_binary_conditions_exception(self):
        """Test lines 537-538: ValueError/AttributeError handling."""

        # Create a mock condition that will cause exceptions in the try block
        class MockCondition:
            def __init__(self):
                self.left = sqlglot.parse_one("age")

            @property
            def right(self):
                # This will cause AttributeError when accessed
                raise AttributeError("Mock attribute error")

        sql_condition = MockCondition()
        perm_condition = sqlglot.parse_one("age > 18")

        # This should trigger the exception handling at lines 537-538
        result = _compare_binary_conditions(sql_condition, perm_condition)
        assert result is False

        # Test a ValueError case as well
        class ValueErrorCondition:
            def __init__(self):
                self.left = sqlglot.parse_one("age")

            @property
            def right(self):
                raise ValueError("Mock value error")

        sql_condition2 = ValueErrorCondition()
        result2 = _compare_binary_conditions(sql_condition2, perm_condition)
        assert result2 is False

    def test_line_548_extract_numeric_value_return_none(self):
        """Test line 548: return None for non-literal expressions."""
        # Test with a column expression (not a literal)
        column_expr = sqlglot.parse_one("age")
        result = _extract_numeric_value(column_expr)
        assert result is None

        # Test with a function call
        func_expr = sqlglot.parse_one("FUNC()")
        result = _extract_numeric_value(func_expr)
        assert result is None

    def test_line_577_lte_operations(self):
        """Test line 577: <= operations comparison."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age <= 18",
            permission="SELECT name FROM users WHERE age <= 25",
        )
        assert result is True  # 18 <= 25, so age <= 18 is more restrictive

    def test_line_581_lte_vs_lt_operations(self):
        """Test line 581: <= vs < operations."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age <= 20",
            permission="SELECT name FROM users WHERE age < 21",
        )
        assert result is True  # age <= 20 is more restrictive than age < 21

    def test_line_585_lt_vs_lte_operations(self):
        """Test line 585: < vs <= operations."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age < 20",
            permission="SELECT name FROM users WHERE age <= 20",
        )
        assert result is True  # age < 20 is more restrictive than age <= 20

    def test_line_591_eq_vs_gte_operations(self):
        """Test line 591: = vs >= operations."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 25",
            permission="SELECT name FROM users WHERE age >= 18",
        )
        assert result is True  # age = 25 satisfies age >= 18

        # Test the boundary case
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 18",
            permission="SELECT name FROM users WHERE age >= 18",
        )
        assert result is True  # age = 18 satisfies age >= 18

        # Test the negative case
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 15",
            permission="SELECT name FROM users WHERE age >= 18",
        )
        assert result is False  # age = 15 doesn't satisfy age >= 18

    def test_line_592_eq_vs_gte_boundary(self):
        """Test line 592: specific boundary for = vs >=."""
        result = _is_more_restrictive("eq", 18.0, "gte", 18.0)
        assert result is True

    def test_line_593_eq_vs_lt_operations(self):
        """Test line 593: = vs < operations."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 15",
            permission="SELECT name FROM users WHERE age < 18",
        )
        assert result is True  # age = 15 satisfies age < 18

        # Test the boundary case
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 20",
            permission="SELECT name FROM users WHERE age < 18",
        )
        assert result is False  # age = 20 doesn't satisfy age < 18

    def test_line_594_eq_vs_lt_boundary(self):
        """Test line 594: specific boundary for = vs <."""
        result = _is_more_restrictive("eq", 15.0, "lt", 18.0)
        assert result is True

    def test_line_595_eq_vs_lte_operations(self):
        """Test line 595: = vs <= operations."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 18",
            permission="SELECT name FROM users WHERE age <= 18",
        )
        assert result is True  # age = 18 satisfies age <= 18

        # Test negative case
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 20",
            permission="SELECT name FROM users WHERE age <= 18",
        )
        assert result is False  # age = 20 doesn't satisfy age <= 18

    def test_line_596_eq_vs_lte_boundary(self):
        """Test line 596: specific boundary for = vs <=."""
        result = _is_more_restrictive("eq", 18.0, "lte", 18.0)
        assert result is True

    def test_line_597_eq_vs_eq_operations(self):
        """Test line 597: = vs = operations."""
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 25",
            permission="SELECT name FROM users WHERE age = 25",
        )
        assert result is True  # Same equality condition

        # Test different values
        result = check_permission(
            sql="SELECT name FROM users WHERE age = 25",
            permission="SELECT name FROM users WHERE age = 30",
        )
        assert result is False  # Different equality values

    def test_line_598_eq_vs_eq_boundary(self):
        """Test line 598: specific boundary for = vs =."""
        result = _is_more_restrictive("eq", 25.0, "eq", 25.0)
        assert result is True

        result = _is_more_restrictive("eq", 25.0, "eq", 30.0)
        assert result is False

    def test_line_599_eq_invalid_perm_op(self):
        """Test line 599: = with invalid permission operator."""
        # This will test operators not handled in the = branch
        result = _is_more_restrictive("eq", 25.0, "ne", 30.0)  # "ne" not handled
        assert result is False  # Should fall through to line 600

    def test_line_600_final_fallback(self):
        """Test line 600: final return False for unhandled operations."""
        # Test with operators that aren't handled by any branch
        result = _is_more_restrictive("ne", 25.0, "like", 30.0)
        assert result is False

        # Test permission operator not handled
        result = _is_more_restrictive("gt", 25.0, "between", 30.0)
        assert result is False


class TestComplexScenarios:
    """Additional complex scenarios to ensure robust coverage."""

    def test_exception_in_numeric_comparison(self):
        """Test additional exception handling scenarios."""

        # Simple test - the exception handling should already be covered
        # by the other tests, this is just a sanity check
        result = check_permission(
            sql="SELECT name FROM users WHERE complex_func(age) > 21",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is False  # Should fall back safely

    def test_non_literal_numeric_extraction(self):
        """Test numeric extraction with various expression types."""
        # Test with literal that can't be converted to float
        literal_expr = sqlglot.exp.Literal.string("'not_a_number'")
        result = _extract_numeric_value(literal_expr)
        assert result is None

        # Test with valid numeric literal
        literal_expr = sqlglot.exp.Literal.number("42.5")
        result = _extract_numeric_value(literal_expr)
        assert result == 42.5

    def test_condition_with_different_columns(self):
        """Test conditions on completely different columns."""
        result = check_permission(
            sql="SELECT name FROM users WHERE department = 'eng'",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is False  # Different columns, should fail

    def test_mixed_condition_types(self):
        """Test mixing different types of conditions."""
        # SQL has numeric condition, permission has string condition
        result = check_permission(
            sql="SELECT name FROM users WHERE age > 21",
            permission="SELECT name FROM users WHERE name = 'John'",
        )
        assert result is False  # Different condition types

    def test_complex_expression_conditions(self):
        """Test conditions with complex expressions that cause exceptions."""
        result = check_permission(
            sql="SELECT name FROM users WHERE COMPLEX_FUNC(age, status) > 21",
            permission="SELECT name FROM users WHERE age > 18",
        )
        assert result is False  # Complex expressions should fall back safely


class TestEdgeCaseBoundaries:
    """Test exact boundary conditions for numeric comparisons."""

    def test_exact_boundary_values(self):
        """Test exact boundary values for all comparison types."""
        # Test >= boundary where SQL value equals permission value
        result = _is_more_restrictive("gte", 21.0, "gt", 20.0)  # age >= 21 vs age > 20
        assert result is True

        # Test < boundary conditions
        result = _is_more_restrictive("lt", 18.0, "lt", 21.0)  # age < 18 vs age < 21
        assert result is True

        # Test <= boundary conditions
        result = _is_more_restrictive(
            "lte", 18.0, "lte", 21.0
        )  # age <= 18 vs age <= 21
        assert result is True

    def test_float_precision_handling(self):
        """Test handling of float precision in comparisons."""
        result = check_permission(
            sql="SELECT name FROM products WHERE price > 100.99",
            permission="SELECT name FROM products WHERE price > 50.50",
        )
        assert result is True

        result = check_permission(
            sql="SELECT name FROM products WHERE price = 75.25",
            permission="SELECT name FROM products WHERE price >= 75.25",
        )
        assert result is True
