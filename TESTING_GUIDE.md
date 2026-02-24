# Testing Guide for PoopyFeed Backend

## Quick Start

```bash
# Full test suite with coverage (for CI/CD)
make test-backend                    # ~53 seconds

# Fast tests without coverage (for development)
make test-backend-fast               # ~45 seconds

# Ultra-fast tests with minimal output
make test-backend-quick              # ~42 seconds

# RECOMMENDED: Parallel execution (pytest + 4 workers)
make test-backend-parallel-fast      # ~15-16 seconds (3.5x faster!)

# Parallel with full output
make test-backend-parallel           # ~16-17 seconds with verbose output

# Parallel with auto-detected CPU cores
make test-backend-parallel-auto      # ~15-20 seconds (depends on CPU)
```

## Test Execution Performance

### Current Baseline (Django test runner)

- **Full suite (with coverage)**: ~53 seconds
- **Fast suite (no coverage)**: ~45 seconds
- **Quick suite (minimal output)**: ~42 seconds

### With Pytest Parallel Execution ⚡ (RECOMMENDED)

- **Parallel with 4 workers**: ~15-16 seconds (3.5x faster!)
- **Parallel with auto-detect**: ~15-20 seconds
- **Parallel with coverage**: ~20-25 seconds
- **Pass rate**: 99.5% (3 tests skip due to Redis timing issues)

### Test Stats

- **Total tests**: 555
- **Coverage**: 98%
- **Passing**: 555 ✅ (with Django runner) / 432+ ✅ (with pytest parallel)
- **Failing**: 0 (Django) / 3 (pytest parallel - known Redis conflicts)

## Optimization Guide

### For Development (Fast Feedback Loop)

Use the fast test command during development:

```bash
make test-backend-fast
```

**Benefits**:

- 15-20% faster than full coverage run
- Still shows full test output
- Perfect for TDD workflow

### For Quick Checks

Use the quick command for ultra-fast checks:

```bash
make test-backend-quick
```

**Benefits**:

- 20-25% faster than fast command
- Minimal output (only failures)
- Great for rapid iteration

### Run Specific Tests

```bash
# Run tests for a specific app
podman compose exec backend python manage.py test analytics.tests

# Run specific test class
podman compose exec backend python manage.py test analytics.tests.PDFDownloadTests

# Run specific test method
podman compose exec backend python manage.py test analytics.tests.PDFDownloadTests.test_download_pdf_invalid_filename_with_slashes

# Run tests matching a pattern
podman compose exec backend python manage.py test --pattern="test_pdf*"
```

## Pytest Parallel Execution (RECOMMENDED) ⚡

### Installation

Pytest is already installed in the container! Use the Makefile targets:

```bash
# Recommended: Fastest for development
make test-backend-parallel-fast     # ~15 seconds, 4 workers

# Full output with parallel
make test-backend-parallel          # ~16 seconds, verbose, 4 workers

# Auto-detect CPU cores (faster on multi-core systems)
make test-backend-parallel-auto     # ~15-20 seconds, depends on CPU
```

### Manual Pytest Commands

```bash
# Parallel with 4 workers (recommended)
pytest -n 4 --dist loadscope

# Auto-detect CPU cores
pytest -n auto --dist loadscope

# Without coverage (faster)
pytest -n 4 --dist loadscope --no-cov -q

# With specific verbosity
pytest -n 4 --dist loadscope -v      # Verbose
pytest -n 4 --dist loadscope -q      # Quiet

# Exclude problematic tests
pytest -n 4 --dist loadscope -m "not parallel_unsafe"

# Specific test file
pytest -n 4 --dist loadscope analytics/tests.py

# Run only failed tests (after previous run)
pytest --lf -n 4 --dist loadscope
```

### Performance Comparison

| Method                          | Time      | Speedup  |
| ------------------------------- | --------- | -------- |
| Django test runner (standard)   | 45-53s    | Baseline |
| Django test runner (fast)       | 42-45s    | 1.15x    |
| Pytest sequential               | ~40s      | 1.2x     |
| Pytest parallel (4 workers) 🚀  | 15-16s    | 3.5x     |
| Pytest parallel (auto)          | 15-20s    | 2.5-3.5x |

### Configuration

See `pytest.ini` for configuration. Key options:

```ini
# Default distribution strategy (groups tests by class)
--dist loadscope

# Number of workers
-n 4                    # 4 workers
-n auto                 # Auto-detect
-n 2                    # Slower but uses less memory

# Coverage
--no-cov               # Skip coverage (faster)
--cov=.                # Include coverage
```

### Known Issues with Parallel Execution

**3 tests fail in parallel** due to Redis timing/state conflicts:

1. `django_project/test_redis_integration.py::RedisCacheCeleryFullIntegrationTests::test_cache_invalidation_propagates_correctly`
2. `django_project/test_redis_integration.py::RedisCacheCeleryFullIntegrationTests::test_redis_survives_multiple_operations`
3. `children/tests.py::RevokeAccessViewTests::test_revoke_access_owner`

**Workaround**: These tests pass in sequential mode or can be skipped:

```bash
# Skip known parallel-unsafe tests
pytest -n 4 --dist loadscope -m "not parallel_unsafe"
```

**Pass Rate**: 99.5% in parallel mode (432/435 tests pass)

## Database Optimization

### Container (GitHub Actions / Docker Compose)

- Uses PostgreSQL (slower but realistic)
- 45-55 seconds for full suite

### Local Development

- Uses SQLite in-memory (faster)
- 25-35 seconds for full suite

To use local SQLite instead of PostgreSQL when running in container:

```bash
unset DATABASE_HOST
make test-backend-fast
```

## Test File Organization

All tests follow Django's recommended structure:

```text
<app>/
├── tests.py          # All tests for the app
├── test_*.py         # Additional test modules (optional)
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_views.py
    └── test_api.py
```

## Performance Tips

### ✅ DO

- Use `setUpTestData` for read-only test data (shared across tests)
- Use `setUp` only for mutable test data
- Mock external APIs and expensive operations
- Use `@override_settings` for temporary setting changes
- Keep individual tests focused and small

### ❌ DON'T

- Create test data in `setUp` when it could be in `setUpTestData`
- Run expensive operations (file I/O, network calls) without mocking
- Disable database transactions unnecessarily
- Create interdependent tests (tests should be independent)

## Profiling Slow Tests

To identify which tests are slowest:

```bash
# With Django test runner (rough timing)
time make test-backend-fast

# With pytest (detailed timing)
pytest --durations=10  # Show 10 slowest tests
```

## CI/CD Integration

### GitHub Actions

The CI/CD pipeline runs:

```bash
make test-backend  # Full coverage + reporting
```

This is slower but ensures complete coverage verification and generates reports for Codecov.

### Development Workflow

Use fast or quick commands for quick feedback:

```bash
make test-backend-fast
```

Then run full coverage periodically:

```bash
make test-backend
```

## Common Issues

### "database is locked" errors

- Usually indicates parallel test issues
- Solution: Run tests sequentially with `pytest` or `make test-backend`

### Flaky tests (inconsistent failures)

- Often caused by test ordering or timing issues
- Solution: Run tests with `--shuffle` to randomize order

### Memory issues with parallel tests

- Solution: Reduce worker count with `-n 2` instead of `-n auto`

## Coverage Goals

- **Target**: 95%+ coverage for critical code
- **Current**: 98% overall coverage
- **Gaps**: URL routing (auto-tested), test configuration (non-critical)

Run coverage report:

```bash
make test-backend
# Coverage report displayed at end
```

View detailed HTML report:

```bash
podman compose exec backend coverage html
# Open htmlcov/index.html in browser
```

## Test Maintenance

### Adding New Tests

1. Follow existing patterns in `tests.py` or `test_*.py`
2. Use descriptive test names: `test_<feature>_<scenario>`
3. Add docstrings explaining what's being tested
4. Use `setUpTestData` for shared data, `setUp` for mutable data
5. Mock external dependencies

### Updating Existing Tests

1. Keep tests independent (no inter-test dependencies)
2. Update fixtures if model structure changes
3. Add new test cases for edge cases
4. Verify coverage doesn't decrease

## References

- [Django Testing Documentation](https://docs.djangoproject.com/en/6.0/topics/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
