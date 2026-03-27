"""
Shared pytest fixtures for PharmaCheck tests.
"""
import pytest
import backend.main as main_module


@pytest.fixture(autouse=True)
def clear_drug_cache():
    """Clear the in-memory drug cache before each test to prevent cross-test contamination."""
    main_module._DRUG_CACHE.clear()
    yield
    main_module._DRUG_CACHE.clear()
