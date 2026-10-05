"""Shared pytest fixtures."""
import itertools

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.components.models import Category, Package, SpecificationDefinition
from apps.manufacturers.models import Manufacturer

_counter = itertools.count(1)
TEST_PASSWORD = "Test-Only-Pass-91x"  # test fixture value, not a real credential


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_user(db):
    def _make(role_code: str | None = None, **extra) -> User:
        n = next(_counter)
        user = User.objects.create_user(
            email=extra.pop("email", f"user{n}@test.local"),
            password=TEST_PASSWORD,
            first_name=extra.pop("first_name", "Test"),
            last_name=extra.pop("last_name", f"User{n}"),
            **extra,
        )
        if role_code:
            user.roles.set([Role.objects.get(code=role_code)])
        return user

    return _make


@pytest.fixture
def client_for(make_user):
    def _client(role_code: str | None = None, user: User | None = None) -> APIClient:
        client = APIClient()
        client.force_authenticate(user or make_user(role_code))
        return client

    return _client


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def capacitor_category(db):
    passives = Category.objects.create(name="Passives", code="PAS")
    cap = Category.objects.create(name="Capacitors", code="CAP", parent=passives)
    SpecificationDefinition.objects.create(
        category=cap, key="capacitance", name="Capacitance", data_type="DECIMAL", unit="F",
        use_si_prefix=True, is_required=True, sort_order=1,
    )
    SpecificationDefinition.objects.create(
        category=cap, key="dielectric", name="Dielectric", data_type="ENUM", enum_choices=["X5R", "X7R", "C0G/NP0"],
        sort_order=2,
    )
    SpecificationDefinition.objects.create(
        category=passives, key="rohs_note", name="RoHS note", data_type="STRING", sort_order=9,
    )
    return cap


@pytest.fixture
def ic_category(db):
    cat = Category.objects.create(name="CAN Transceivers", code="IC-CAN")
    SpecificationDefinition.objects.create(
        category=cat, key="automotive", name="Automotive", data_type="BOOLEAN", sort_order=1
    )
    return cat


@pytest.fixture
def ti(db):
    return Manufacturer.objects.create(name="Texas Instruments", short_name="TI")


@pytest.fixture
def soic8(db):
    return Package.objects.create(name="SOIC-8", pin_count=8)
