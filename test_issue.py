#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')
from sigill.api import check_permission

result = check_permission(
    sql="SELECT name FROM users WHERE age > 21",
    permission="SELECT name, age FROM users WHERE age > 18"
)
print(f'Result: {result}')
print('This should be True because age > 21 is more restrictive than age > 18')

# Let's debug why this is failing
from sigill.api import _parse_expression, _is_where_subset
import sqlglot

sql_expr = _parse_expression("SELECT name FROM users WHERE age > 21")
perm_expr = _parse_expression("SELECT name, age FROM users WHERE age > 18")

print(f"\nSQL WHERE clause: {sql_expr.args.get('where')}")
print(f"Permission WHERE clause: {perm_expr.args.get('where')}")

# Test the WHERE subset check specifically
where_result = _is_where_subset(sql_expr, perm_expr)
print(f"\nWHERE subset check result: {where_result}")