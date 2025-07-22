# sigill
Sigill prevents unauthorized SQL. Sigill only understand SQL.

<img src="sigill.png" />

## Examples

Imagine you've created a dashboard in [Apache Superset](https://superset.apache.org/) with a chart showing how many people with a given last name and within a given age range exist in each country. The query behind the chart might look like this:

```sql
SELECT
    country, last_name, age_bucket, COUNT(*)
FROM
    dim_users
WHERE
    last_name = 'Lee'
GROUP BY
    country, last_name, age_bucket;
```

You share the dashboard with a co-worker who doesn't haven't access to the underlying table. The co-worker is not interested in age buckets, so they modify the query to:

```sql
SELECT
    country, last_name, COUNT(*)
FROM
    dim_users
WHERE
    last_name = 'Lee'
GROUP BY
    country, last_name;
```

This should be fine to run, since the second query is a subset of the first query. However, the co-worker shouldn't be able to look at data for a different last name:

```sql
SELECT
    country, last_name, COUNT(*)
FROM
    dim_users
WHERE
    last_name = 'Smith'
GROUP BY
    country, last_name;
```

Even some simpler queries shouldn't be allowed:

```sql
SELECT COUNT(*) FROM dim_users;
```

While this one should be allowed:

```sql
SELECT COUNT(*) FROM dim_users WHERE last_name = 'Lee';
```

**Sigill** is a library that checks if a given query is a subquery of a set of allowed queries. It does this by parsing the queries into an abstract syntax tree (AST) and comparing the ASTs in a semantic way.

Additionally, it can be configured to modify queries so that they match the allowed queries. For example, if a user is allowed to run this query:

```sql
SELECT
    ANONYMIZE(last_name), age, preferred_color
FROM
    users;
```

Then a query like this one:

```sql
SELECT last_name, age FROM users WHERE age = MAX(age);
```

Would be converted to:

```sql
SELECT ANONYMIZE(last_name), age FROM users WHERE age = MAX(age);
```

### Joins

```sql
SELECT
    MAX(salary)
FROM
    payroll
JOIN
    employees
ON
    payroll.employee_id = employees.id
WHERE
    employees.department = 'Engineering'
```
