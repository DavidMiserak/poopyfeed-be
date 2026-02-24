"""
Common test constants shared across all test files.

Centralizing these values helps reduce SonarQube security hotspots
while maintaining consistent test data across the test suite.
"""

# Test user credentials
TEST_PASSWORD = (
    "testpass123"  # noqa: S105  # nosec B105 - Test password, not a security issue
)

# Test passwords for password change/validation tests
TEST_NEW_SECURE_PASSWORD = (
    "NewSecurePass123!"  # noqa: S105  # nosec B105 - Test password
)
TEST_WRONG_PASSWORD = "wrongpassword"  # noqa: S105  # nosec B105 - Test password
TEST_DIFFERENT_PASSWORD = (
    "DifferentPass123!"  # noqa: S105  # nosec B105 - Test password
)
TEST_WEAK_PASSWORD = "123"  # noqa: S105  # nosec B105 - Test password
TEST_COMMON_PASSWORD = "password123"  # noqa: S105  # nosec B105 - Test password
