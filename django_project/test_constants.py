"""
Common test constants shared across all test files.

Centralizing these values helps reduce SonarQube security hotspots
while maintaining consistent test data across the test suite.
"""

# Test user credentials
TEST_PASSWORD = (
    "testpass123"  # noqa: S105  # nosec B105 - Test password, not a security issue
)
