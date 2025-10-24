"""Tests for security utilities."""

import pytest

from app.core.security import (
    create_access_token,
    get_password_hash,
    validate_password_strength,
    verify_password,
    verify_token,
)


def test_password_hashing():
    """Test password hashing and verification."""
    password = "TestPassword123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)


def test_token_creation_and_verification():
    """Test JWT token creation and verification."""
    user_id = "12345"
    token = create_access_token(user_id)

    assert token is not None
    assert isinstance(token, str)

    verified_id = verify_token(token, token_type="access")
    assert verified_id == user_id


def test_invalid_token_verification():
    """Test verification of invalid token."""
    invalid_token = "invalid.token.here"
    verified_id = verify_token(invalid_token)

    assert verified_id is None


@pytest.mark.parametrize(
    ("password", "expected_valid"),
    [
        ("Test123!", True),
        ("weak", False),  # Too short
        ("NoDigits!", False),  # No digits
        ("nouppercas3!", False),  # No uppercase
        ("NOLOWERCASE3!", False),  # No lowercase
        ("NoSpecial123", False),  # No special char
    ],
)
def test_password_strength_validation(password: str, expected_valid: bool):
    """Test password strength validation."""
    is_valid, _ = validate_password_strength(password)
    assert is_valid == expected_valid
