# Test Suite Organization

This directory contains comprehensive tests for the sigill SQL authorization library, organized by functionality rather than coverage milestones.

## Test Files Overview

### Core API Tests
- **`test_api.py`** - Main API functions (`check`, `check_permission`, `tighten`) and basic functionality
- **`test_complex_queries.py`** - Complex SQL constructs (UNION, CTEs, JOINs, subqueries, window functions)

### Permission Validation Tests  
- **`test_wildcard_patterns.py`** - Wildcard table permission matching (`*.table`, `catalog.*.*`, etc.)
- **`test_column_validation.py`** - Column validation, ANONYMIZE functions, and GROUP BY checks
- **`test_condition_extraction.py`** - WHERE condition parsing, AND extraction, query scoring
- **`test_expression_matching.py`** - SQL expression matching and permission validation

### Specialized Function Tests
- **`test_window_functions.py`** - Window function validation and CTE handling
- **`test_anonymize_functions.py`** - ANONYMIZE function processing and tighten operations
- **`test_helper_functions.py`** - Low-level helper functions and internal utilities

### Edge Cases & Error Handling
- **`test_edge_cases.py`** - Exception handling, boundary conditions, and mock scenarios

## Test Coverage

The test suite maintains **100% code coverage** across:
- **160 comprehensive tests** covering all functionality
- **Every line of code** tested with edge cases
- **Production-ready** reliability and error handling
- **Complex SQL scenarios** including all major SQL constructs

## Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/sigill --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_api.py

# Run tests with verbose output
uv run pytest -v
```

## Test Organization Principles

1. **Functionality-based grouping** - Tests organized by what they validate, not by coverage goals
2. **Clear naming** - File names clearly indicate the area of functionality being tested  
3. **Comprehensive coverage** - Every edge case, error condition, and code path tested
4. **Maintainable structure** - Easy to find and add tests for specific features