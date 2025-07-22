"""
Sigill prevents unauthorized SQL. Sigill only understand SQL.

Sigill is a SQL authorization library. Data access permissions are expressed as SQL
queries, and arbitrary queries are checked against these permissions. Permissions can be
as permissive as:

    SELECT * FROM catalog."*"."*";

Or as restrictive as:

    SELECT MIN(salary) FROM employees WHERE department = 'engineering';

"""

import sqlglot
from typing import Union, Optional

# Type aliases for better readability (Explicit is better than implicit)
SQLExpression = Union[str, sqlglot.Expression]
CompoundStatement = Union[sqlglot.exp.Union, sqlglot.exp.Intersect, sqlglot.exp.Except]

# Constants for aggregate function detection (Readability counts)
AGGREGATE_FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}


def check(sql: SQLExpression, permissions: set[SQLExpression]) -> bool:
    """Check if a SQL query is authorized by any permission in a set."""
    return any(check_permission(sql, permission) for permission in permissions)


def check_permission(sql: SQLExpression, permission: SQLExpression) -> bool:
    """Check if a SQL query is authorized by a specific permission."""
    sql_expr = _parse_expression(sql)
    perm_expr = _parse_expression(permission)

    # Handle compound statements (UNION, INTERSECT, EXCEPT)
    if _is_compound_statement(sql_expr):
        return _check_compound_statement(sql_expr, perm_expr)  # type: ignore

    if _is_compound_statement(perm_expr):
        return _check_against_compound_permission(sql_expr, perm_expr)  # type: ignore

    # Both must be SELECT statements for direct comparison
    if not _are_both_select_statements(sql_expr, perm_expr):
        return False

    return _check_select_permission(sql_expr, perm_expr)  # type: ignore


def tighten(sql: SQLExpression, permissions: set[SQLExpression]) -> sqlglot.Expression:
    """
    Tighten a SQL query to conform to the best matching permission.

    This function modifies the SQL to conform to permissions. For example:

    SQL:        SELECT a, b, c FROM users WHERE salary < 2000
    Permission: SELECT a, ANONYMIZE(c) FROM users WHERE id = 1 AND salary < 1000
    Result:     SELECT a, NULL, ANONYMIZE(c) FROM users WHERE id = 1 AND salary < 1000
    """
    sql_expr = _parse_expression(sql)

    if _is_compound_statement(sql_expr):
        raise ValueError("Tighten function does not support compound statements")

    if not isinstance(sql_expr, sqlglot.exp.Select):
        raise ValueError("Input must be a SELECT statement")

    best_permission = _find_best_matching_permission(sql_expr, permissions)
    return _apply_permission_constraints(sql_expr, best_permission)


# Private helper functions (following the principle of "one obvious way to do it")


def _parse_expression(expr: SQLExpression) -> sqlglot.Expression:
    """Parse a string or return the expression if already parsed."""
    return expr if isinstance(expr, sqlglot.Expression) else sqlglot.parse_one(expr)


def _is_compound_statement(expr: sqlglot.Expression) -> bool:
    """Check if expression is a compound statement (UNION, INTERSECT, EXCEPT)."""
    return isinstance(
        expr, (sqlglot.exp.Union, sqlglot.exp.Intersect, sqlglot.exp.Except)
    )


def _are_both_select_statements(
    expr1: sqlglot.Expression, expr2: sqlglot.Expression
) -> bool:
    """Check if both expressions are SELECT statements."""
    return isinstance(expr1, sqlglot.exp.Select) and isinstance(
        expr2, sqlglot.exp.Select
    )


def _check_select_permission(
    sql: sqlglot.exp.Select, permission: sqlglot.exp.Select
) -> bool:
    """Check if a SELECT query is authorized by a SELECT permission."""
    # All validation checks must pass (Simple is better than complex)
    validations = [
        _is_table_subset(sql, permission),
        _is_column_subset(sql, permission),
        _is_where_subset(sql, permission),
        _is_group_by_subset(sql, permission),
        _is_having_subset(sql, permission),
    ]
    return all(validations)


def _check_compound_statement(
    sql: CompoundStatement, permission: sqlglot.Expression
) -> bool:
    """
    Check if a compound statement is authorized.
    Each component must be individually authorized.
    """
    select_statements = _extract_select_statements(sql)
    return all(check_permission(stmt, permission) for stmt in select_statements)


def _check_against_compound_permission(
    sql: sqlglot.Expression, permission: CompoundStatement
) -> bool:
    """
    Check if a query is authorized against a compound permission.
    Query must be authorized by at least one component.
    """
    permission_statements = _extract_select_statements(permission)
    return any(check_permission(sql, perm_stmt) for perm_stmt in permission_statements)


def _extract_select_statements(compound: CompoundStatement) -> list[sqlglot.exp.Select]:
    """Extract all SELECT statements from a compound statement."""
    statements: list[sqlglot.exp.Select] = []

    def extract_recursive(expr: sqlglot.Expression) -> None:
        if isinstance(expr, sqlglot.exp.Select):
            statements.append(expr)
        elif _is_compound_statement(expr):
            # Type narrowing - we know it's a compound statement
            compound_expr = expr  # type: ignore[attr-defined]
            extract_recursive(compound_expr.left)  # type: ignore[attr-defined]
            extract_recursive(compound_expr.right)  # type: ignore[attr-defined]
        elif hasattr(expr, "this") and expr.this:
            extract_recursive(expr.this)

    extract_recursive(compound)
    return statements


def _find_best_matching_permission(
    sql: sqlglot.exp.Select, permissions: set[SQLExpression]
) -> sqlglot.exp.Select:
    """Find the permission with the highest matching score."""
    best_permission = None
    best_score = -1

    for perm in permissions:
        perm_expr = _parse_expression(perm)
        if not isinstance(perm_expr, sqlglot.exp.Select):
            continue

        score = _calculate_match_score(sql, perm_expr)
        if score > best_score:
            best_score = score
            best_permission = perm_expr

    if best_permission is None or best_score < 1:
        raise ValueError("No matching permission found")

    return best_permission


def _is_table_subset(sql: sqlglot.exp.Select, permission: sqlglot.exp.Select) -> bool:
    """Check if query tables are allowed by permission tables."""
    sql_tables = set(_get_table_names(sql))
    perm_tables = set(_get_table_names(permission))

    if not sql_tables:
        return False

    # Check wildcard permissions first (optimization)
    if _check_wildcard_permissions(sql_tables, perm_tables):
        return True

    return sql_tables.issubset(perm_tables)


def _check_wildcard_permissions(sql_tables: set[str], perm_tables: set[str]) -> bool:
    """Check if wildcard permissions allow the SQL tables."""
    for perm_table in perm_tables:
        if "*" not in perm_table:
            continue

        if _matches_wildcard_pattern(sql_tables, perm_table):
            return True

    return False


def _matches_wildcard_pattern(sql_tables: set[str], perm_table: str) -> bool:
    """Check if SQL tables match a wildcard permission pattern."""
    # Simple wildcard matches any table
    if perm_table == "*":
        return True

    perm_parts = perm_table.split(".")

    if len(perm_parts) == 3:
        return _matches_three_part_wildcard(sql_tables, perm_parts)
    elif len(perm_parts) == 2:
        return _matches_two_part_wildcard(sql_tables, perm_parts)

    return False


def _matches_three_part_wildcard(sql_tables: set[str], perm_parts: list[str]) -> bool:
    """Check three-part wildcard pattern (catalog.db.table)."""
    catalog, db, table = perm_parts

    if catalog == "*":
        return True

    for sql_table in sql_tables:
        sql_parts = sql_table.split(".")

        if len(sql_parts) == 3:
            if _parts_match(sql_parts, perm_parts):
                return True
        elif len(sql_parts) == 2 and db == "*":
            return True
        elif len(sql_parts) == 1 and db == "*" and table == "*":
            return True

    return False


def _matches_two_part_wildcard(sql_tables: set[str], perm_parts: list[str]) -> bool:
    """Check two-part wildcard pattern (db.table)."""
    db, table = perm_parts

    for sql_table in sql_tables:
        sql_parts = sql_table.split(".")

        if len(sql_parts) >= 2:
            if _wildcard_or_equal(db, sql_parts[-2]) and _wildcard_or_equal(
                table, sql_parts[-1]
            ):
                return True
        elif len(sql_parts) == 1 and table == "*":
            return True

    return False


def _parts_match(sql_parts: list[str], perm_parts: list[str]) -> bool:
    """Check if SQL parts match permission parts (allowing wildcards)."""
    return all(
        _wildcard_or_equal(perm_part, sql_part)
        for perm_part, sql_part in zip(perm_parts, sql_parts)
    )


def _wildcard_or_equal(perm_part: str, sql_part: str) -> bool:
    """Check if permission part matches SQL part (wildcard or exact match)."""
    return perm_part == "*" or perm_part == sql_part


def _get_table_names(expression: sqlglot.Expression) -> list[str]:
    """Extract table names from any SQL expression."""
    # Handle compound statements recursively
    if _is_compound_statement(expression):
        return _get_compound_table_names(expression)  # type: ignore

    # Get regular table names and filter out CTEs
    tables = _extract_table_references(expression)
    cte_names = _get_cte_names(expression)

    return [table for table in tables if _table_name_from_path(table) not in cte_names]


def _get_compound_table_names(expression: CompoundStatement) -> list[str]:
    """Get table names from compound statements."""
    tables = []
    select_statements = _extract_select_statements(expression)

    for select_stmt in select_statements:
        tables.extend(_get_table_names(select_stmt))

    return list(set(tables))  # Remove duplicates


def _extract_table_references(expression: sqlglot.Expression) -> list[str]:
    """Extract table references from expression."""
    tables = []

    # Add CTE table definitions
    if hasattr(expression, "ctes") and expression.ctes:
        for cte in expression.ctes:
            tables.extend(_get_table_names(cte.this))

    # Add regular table references
    for table in expression.find_all(sqlglot.exp.Table):
        table_path = _build_table_path(table)
        tables.append(table_path)

    return tables


def _build_table_path(table: sqlglot.exp.Table) -> str:
    """Build full table path from table parts."""
    parts = []
    if table.catalog:
        parts.append(table.catalog)
    if table.db:
        parts.append(table.db)
    parts.append(table.name)
    return ".".join(parts)


def _get_cte_names(expression: sqlglot.Expression) -> set[str]:
    """Get CTE names from expression."""
    cte_names = set()
    if hasattr(expression, "ctes") and expression.ctes:
        for cte in expression.ctes:
            cte_names.add(cte.alias)
    return cte_names


def _table_name_from_path(table_path: str) -> str:
    """Extract table name from full path (last part after dots)."""
    return table_path.split(".")[-1]


def _is_column_subset(sql: sqlglot.exp.Select, permission: sqlglot.exp.Select) -> bool:
    """Check if query columns are allowed by permission columns."""
    sql_projections = _get_projections(sql)
    perm_projections = _get_projections(permission)

    # Wildcard permission allows all columns
    if "*" in perm_projections:
        return True

    # Check each SQL projection against permissions
    for sql_proj in sql_projections:
        if not _is_projection_allowed(sql_proj, perm_projections):
            return False

    return True


def _is_projection_allowed(sql_proj: str, perm_projections: list[str]) -> bool:
    """Check if a single projection is allowed by permissions."""
    # Star projection requires star permission
    if sql_proj == "*":
        return "*" in perm_projections

    # Check window functions first (special case handling)
    if _is_window_function_allowed(sql_proj, perm_projections):
        return True

    # Check against each permission projection
    return any(
        _is_column_allowed(sql_proj, perm_proj) for perm_proj in perm_projections
    )


def _is_window_function_allowed(sql_proj: str, perm_projections: list[str]) -> bool:
    """Check if window function projection is allowed."""
    try:
        sql_expr = sqlglot.parse_one(sql_proj)
        is_window = (
            isinstance(sql_expr, sqlglot.exp.Window) or "OVER" in sql_proj.upper()
        )

        if is_window:
            return _validate_window_function_columns(sql_expr, perm_projections)
    except Exception:
        pass

    return False


def _get_projections(select: sqlglot.exp.Select) -> list[str]:
    """Extract column projections from SELECT statement."""
    projections = []
    for expr in select.expressions:
        if isinstance(expr, sqlglot.exp.Star):
            projections.append("*")
        else:
            projections.append(expr.sql())
    return projections


def _is_column_allowed(sql_col: str, perm_col: str) -> bool:
    """Check if a column expression is allowed by permission."""
    # Wildcard permission allows anything
    if perm_col == "*":
        return True

    # Exact string match
    if sql_col == perm_col:
        return True

    # Parse and compare expressions
    return _are_column_expressions_allowed(sql_col, perm_col)


def _are_column_expressions_allowed(sql_col: str, perm_col: str) -> bool:
    """Check if parsed column expressions are allowed."""
    try:
        sql_expr = sqlglot.parse_one(sql_col)
        perm_expr = sqlglot.parse_one(perm_col)

        # Special handling for ANONYMIZE functions
        if _is_anonymize_permission(perm_col, perm_expr):
            return _check_anonymize_permission(sql_expr, perm_expr)  # type: ignore

        # Column name comparison
        if _are_both_columns(sql_expr, perm_expr):
            return sql_expr.name == perm_expr.name

        # General expression equality
        return _expressions_equal(sql_expr, perm_expr)

    except Exception:
        return False


def _is_anonymize_permission(perm_col: str, perm_expr: sqlglot.Expression) -> bool:
    """Check if permission is an ANONYMIZE function."""
    return (
        "ANONYMIZE" in perm_col
        and isinstance(perm_expr, sqlglot.exp.Anonymous)
        and perm_expr.this == "ANONYMIZE"
    )


def _check_anonymize_permission(
    sql_expr: sqlglot.Expression, perm_expr: sqlglot.exp.Anonymous
) -> bool:
    """Check if SQL expression matches ANONYMIZE permission."""
    if not perm_expr.expressions:
        return False

    inner_expr = perm_expr.expressions[0]

    if _are_both_columns(sql_expr, inner_expr):
        return sql_expr.name == inner_expr.name

    return sql_expr.sql() == inner_expr.sql()


def _are_both_columns(expr1: sqlglot.Expression, expr2: sqlglot.Expression) -> bool:
    """Check if both expressions are column references."""
    return isinstance(expr1, sqlglot.exp.Column) and isinstance(
        expr2, sqlglot.exp.Column
    )


def _validate_window_function_columns(
    window_expr: sqlglot.Expression, permission_columns: list[str]
) -> bool:
    """Validate that all columns in window function are allowed."""
    columns_in_window = [col.name for col in window_expr.find_all(sqlglot.exp.Column)]

    # Empty column list is allowed
    if not columns_in_window:
        return True

    # All columns must be allowed
    return all(
        any(_is_column_allowed(col_name, perm_col) for perm_col in permission_columns)
        for col_name in columns_in_window
    )


def _is_where_subset(sql: sqlglot.exp.Select, permission: sqlglot.exp.Select) -> bool:
    """Check if WHERE conditions are more restrictive than permission."""
    sql_where = sql.args.get("where")
    perm_where = permission.args.get("where")

    # No permission WHERE clause means no restrictions
    if not perm_where:
        return True

    # Permission has WHERE but query doesn't - not allowed
    if not sql_where:
        return False

    # Validate subqueries in WHERE clause
    if not _validate_where_subqueries(sql_where, permission):
        return False

    # Check that all permission conditions are present in SQL
    return _all_permission_conditions_present(sql_where, perm_where)


def _condition_satisfies_permission(
    sql_condition: sqlglot.Expression, perm_condition: sqlglot.Expression
) -> bool:
    """Check if SQL condition satisfies (is more restrictive than) permission condition."""
    # First check for exact match
    if _expressions_equal(sql_condition, perm_condition):
        return True

    # Handle comparison operations (>, <, >=, <=, =)
    if isinstance(sql_condition, sqlglot.exp.Binary) and isinstance(
        perm_condition, sqlglot.exp.Binary
    ):
        return _compare_binary_conditions(sql_condition, perm_condition)

    return False


def _compare_binary_conditions(
    sql_condition: sqlglot.exp.Binary, perm_condition: sqlglot.exp.Binary
) -> bool:
    """Compare binary conditions to see if SQL is more restrictive than permission."""
    # Must be operations on the same column/expression
    if not _expressions_equal(sql_condition.left, perm_condition.left):
        return False

    # Extract operators and values
    sql_op = type(sql_condition).__name__.lower()
    perm_op = type(perm_condition).__name__.lower()

    # Try to extract numeric values for comparison
    try:
        sql_value = _extract_numeric_value(sql_condition.right)
        perm_value = _extract_numeric_value(perm_condition.right)

        if sql_value is None or perm_value is None:
            return False

        return _is_more_restrictive(sql_op, sql_value, perm_op, perm_value)
    except (ValueError, AttributeError):
        return False


def _extract_numeric_value(expr: sqlglot.Expression) -> Optional[float]:
    """Extract numeric value from an expression."""
    if isinstance(expr, sqlglot.exp.Literal):
        try:
            return float(expr.this)
        except ValueError:
            return None
    return None


def _is_more_restrictive(
    sql_op: str, sql_value: float, perm_op: str, perm_value: float
) -> bool:
    """Check if SQL condition is more restrictive than permission condition."""
    # Handle > operations: age > 21 is more restrictive than age > 18
    if perm_op == "gt" and sql_op == "gt":
        return sql_value >= perm_value

    # Handle >= operations: age >= 21 is more restrictive than age >= 18
    if perm_op == "gte" and sql_op == "gte":
        return sql_value >= perm_value

    # Handle >= vs >: age >= 22 is more restrictive than age > 21
    if perm_op == "gt" and sql_op == "gte":
        return sql_value >= perm_value + 1

    # Handle > vs >=: age > 21 is more restrictive than age >= 21
    if perm_op == "gte" and sql_op == "gt":
        return sql_value >= perm_value

    # Handle < operations: age < 18 is more restrictive than age < 21
    if perm_op == "lt" and sql_op == "lt":
        return sql_value <= perm_value

    # Handle <= operations: age <= 18 is more restrictive than age <= 21
    if perm_op == "lte" and sql_op == "lte":
        return sql_value <= perm_value

    # Handle <= vs <: age <= 20 is more restrictive than age < 21
    if perm_op == "lt" and sql_op == "lte":
        return sql_value <= perm_value - 1

    # Handle < vs <=: age < 21 is more restrictive than age <= 21
    if perm_op == "lte" and sql_op == "lt":
        return sql_value <= perm_value

    # Handle = operations: age = 20 is more restrictive than age > 18
    if sql_op == "eq":
        if perm_op == "gt":
            return sql_value > perm_value
        elif perm_op == "gte":
            return sql_value >= perm_value
        elif perm_op == "lt":
            return sql_value < perm_value
        elif perm_op == "lte":
            return sql_value <= perm_value
        elif perm_op == "eq":
            return sql_value == perm_value

    return False


def _all_permission_conditions_present(
    sql_where: sqlglot.exp.Where, perm_where: sqlglot.exp.Where
) -> bool:
    """Check that all permission conditions are satisfied by SQL WHERE clause."""
    perm_conditions = _extract_and_conditions(perm_where)
    sql_conditions = _extract_and_conditions(sql_where)

    return all(
        any(
            _condition_satisfies_permission(sql_cond, perm_cond)
            for sql_cond in sql_conditions
        )
        for perm_cond in perm_conditions
    )


def _validate_where_subqueries(
    where: sqlglot.exp.Where, permission: sqlglot.exp.Select
) -> bool:
    """Validate that subqueries in WHERE clause are authorized."""
    subqueries = where.find_all(sqlglot.exp.Select)
    permission_tables = set(_get_table_names(permission))
    has_wildcard = any("*" in table for table in permission_tables)

    for subquery in subqueries:
        subquery_tables = set(_get_table_names(subquery))

        # Subquery tables must be allowed by permission
        if not subquery_tables.issubset(permission_tables) and not has_wildcard:
            return False

    return True


def _extract_and_conditions(where: sqlglot.exp.Where) -> list[sqlglot.Expression]:
    """Extract AND conditions from WHERE clause."""
    conditions: list[sqlglot.Expression] = []
    expr = where.this

    if isinstance(expr, sqlglot.exp.And):
        _extract_conditions_recursively(expr, conditions)
    else:
        conditions.append(expr)

    return conditions


def _extract_conditions_recursively(
    and_expr: sqlglot.exp.And, conditions: list[sqlglot.Expression]
) -> None:
    """Recursively extract conditions from nested AND expressions."""
    # Process left side
    if isinstance(and_expr.left, sqlglot.exp.And):
        _extract_conditions_recursively(and_expr.left, conditions)
    else:
        conditions.append(and_expr.left)

    # Process right side
    if isinstance(and_expr.right, sqlglot.exp.And):
        _extract_conditions_recursively(and_expr.right, conditions)
    else:
        conditions.append(and_expr.right)


def _expressions_equal(expr1: sqlglot.Expression, expr2: sqlglot.Expression) -> bool:
    """Check if two expressions are semantically equal."""
    return expr1.sql() == expr2.sql()


def _is_group_by_subset(
    sql: sqlglot.exp.Select, permission: sqlglot.exp.Select
) -> bool:
    """Check if GROUP BY in SQL is valid based on permission."""
    sql_group = sql.args.get("group")
    perm_group = permission.args.get("group")

    # No permission GROUP BY means no restrictions
    if not perm_group:
        return True

    # Permission has GROUP BY but query doesn't - check for aggregates
    if not sql_group:
        return _has_aggregate_functions(sql)

    # All SQL GROUP BY columns must be in permission GROUP BY
    sql_groups = _get_group_by_columns(sql_group)
    perm_groups = _get_group_by_columns(perm_group)

    return all(sql_grp in perm_groups for sql_grp in sql_groups)


def _has_aggregate_functions(sql: sqlglot.exp.Select) -> bool:
    """Check if SQL query has aggregate functions."""
    return any(
        any(func in expr.sql() for func in AGGREGATE_FUNCTIONS)
        for expr in sql.expressions
    )


def _get_group_by_columns(group: sqlglot.exp.Group) -> list[str]:
    """Extract column names from GROUP BY clause."""
    groups = []
    for expr in group.expressions:
        if isinstance(expr, sqlglot.exp.Column):
            groups.append(expr.name)
        else:
            groups.append(expr.sql())
    return groups


def _is_having_subset(sql: sqlglot.exp.Select, permission: sqlglot.exp.Select) -> bool:
    """Check if HAVING conditions are compatible."""
    perm_having = permission.args.get("having")

    # No permission HAVING means no restrictions
    if not perm_having:
        return True

    # Permission has HAVING but query doesn't - not allowed
    sql_having = sql.args.get("having")
    return sql_having is not None


def _calculate_match_score(
    sql: sqlglot.exp.Select, permission: sqlglot.exp.Select
) -> int:
    """Calculate how well a query matches a permission (higher is better)."""
    score = 0

    # Score table matching
    score += _score_table_match(sql, permission)

    # Score WHERE clause matching
    score += _score_where_match(sql, permission)

    return score


def _score_table_match(sql: sqlglot.exp.Select, permission: sqlglot.exp.Select) -> int:
    """Score table matching between SQL and permission."""
    sql_tables = set(_get_table_names(sql))
    perm_tables = set(_get_table_names(permission))

    if sql_tables == perm_tables:
        return 10
    elif sql_tables.issubset(perm_tables):
        return 5
    else:
        return 0


def _score_where_match(sql: sqlglot.exp.Select, permission: sqlglot.exp.Select) -> int:
    """Score WHERE clause matching between SQL and permission."""
    sql_where = sql.args.get("where")
    perm_where = permission.args.get("where")

    if not (sql_where and perm_where):
        return 0

    sql_conditions = _extract_and_conditions(sql_where)
    perm_conditions = _extract_and_conditions(perm_where)

    score = 0
    for perm_cond in perm_conditions:
        if any(_expressions_equal(sql_cond, perm_cond) for sql_cond in sql_conditions):
            score += 2

    return score


def _apply_permission_constraints(
    sql: sqlglot.exp.Select, permission: sqlglot.exp.Select
) -> sqlglot.exp.Select:
    """Apply permission constraints to create a tightened query."""
    # Build new projections based on permission
    new_projections = _build_constrained_projections(sql, permission)

    # Create result query
    result = sqlglot.exp.Select().select(*new_projections)

    # Copy clauses from permission
    _copy_permission_clauses(result, permission)

    return result


def _build_constrained_projections(
    sql: sqlglot.exp.Select, permission: sqlglot.exp.Select
) -> list[sqlglot.exp.Expression]:
    """Build projections for tightened query based on permission."""
    # Handle wildcard permission - if permission has *, use SQL projections
    if any(isinstance(expr, sqlglot.exp.Star) for expr in permission.expressions):
        return [expr.copy() for expr in sql.expressions]

    new_projections = []

    for perm_expr in permission.expressions:
        matching_expr = _find_matching_expression(perm_expr, sql.expressions)

        if matching_expr:
            new_projections.append(perm_expr.copy())
        # Skip unmatched expressions instead of adding NULL

    # If no projections match, this means the query cannot be tightened properly
    # This should have been caught earlier by permission checking
    if not new_projections:
        raise ValueError("No matching projections found between SQL and permission")

    return new_projections


def _find_matching_expression(
    perm_expr: sqlglot.Expression, sql_expressions: list[sqlglot.Expression]
) -> Optional[sqlglot.Expression]:
    """Find matching expression in SQL for the permission expression."""
    if isinstance(perm_expr, sqlglot.exp.Column):
        return _find_matching_column(perm_expr, sql_expressions)

    if _is_anonymize_expression(perm_expr):
        return _find_matching_anonymize_expression(perm_expr, sql_expressions)  # type: ignore

    # General expression matching
    for sql_expr in sql_expressions:
        if _expressions_equal(sql_expr, perm_expr):
            return sql_expr

    return None


def _find_matching_column(
    perm_expr: sqlglot.exp.Column, sql_expressions: list[sqlglot.Expression]
) -> Optional[sqlglot.Expression]:
    """Find matching column in SQL expressions."""
    for sql_expr in sql_expressions:
        if isinstance(sql_expr, sqlglot.exp.Column) and sql_expr.name == perm_expr.name:
            return sql_expr
    return None


def _is_anonymize_expression(expr: sqlglot.Expression) -> bool:
    """Check if expression is an ANONYMIZE function."""
    return (
        isinstance(expr, sqlglot.exp.Anonymous)
        and expr.this == "ANONYMIZE"
        and bool(expr.expressions)
    )


def _find_matching_anonymize_expression(
    perm_expr: sqlglot.exp.Anonymous, sql_expressions: list[sqlglot.Expression]
) -> Optional[sqlglot.Expression]:
    """Find matching expression for ANONYMIZE permission."""
    inner_col = perm_expr.expressions[0]

    if isinstance(inner_col, sqlglot.exp.Column):
        return _find_matching_column(inner_col, sql_expressions)

    return None


def _copy_permission_clauses(
    result: sqlglot.exp.Select, permission: sqlglot.exp.Select
) -> None:
    """Copy FROM, WHERE, GROUP BY, and HAVING clauses from permission to result."""
    clauses = ["from", "where", "group", "having"]

    for clause_name in clauses:
        clause = permission.args.get(clause_name)
        if clause:
            result.set(clause_name, clause.copy())
