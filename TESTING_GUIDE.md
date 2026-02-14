# Testing Guide for PoopyFeed Backend

## Quick Start

```bash
# Full test suite with coverage (for CI/CD)
make test-backend

# Fast tests without coverage (for development)
make test-backend-fast

# Ultra-fast tests with minimal output
make test-backend-quick
```

## Test Execution Performance

### Current Baseline
- **Full suite (with coverage)**: ~53 seconds
- **Fast suite (no coverage)**: ~45 seconds
- **Quick suite (minimal output)**: ~42 seconds

### Test Stats
- **Total tests**: 555
- **Coverage**: 98%
- **Passing**: 555 ✅
- **Failing**: 0

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

## Advanced: Pytest Setup (Optional)

For even faster parallel execution, you can optionally use pytest:

### Installation

```bash
cd back-end
pip install pytest pytest-django pytest-xdist pytest-timeout pytest-cov
```

### Run with Pytest

```bash
# Single-threaded (baseline)
pytest

# Parallel (auto-detect CPU cores)
pytest -n auto

# Parallel with 4 workers
pytest -n 4

# Fast parallel without coverage
pytest -n auto -p no:cov

# Specific tests
pytest analytics/tests.py::PDFDownloadTests::test_download_pdf_success

# With coverage
pytest --cov --cov-report=html --cov-report=term
```

### Expected Performance with Pytest + Parallel

On 4-core machine:
- **Sequential**: 45-50 seconds
- **Parallel (pytest -n 4)**: 15-20 seconds (3-4x faster)

**Caveat**: Some tests may fail in parallel due to database constraints. Run sequentially if issues occur.

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

```
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

### Local Development
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
