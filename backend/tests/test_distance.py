from decimal import Decimal

from app.modules.delivery_points.service import haversine_distance_m


def test_haversine_distance_is_deterministic() -> None:
    assert haversine_distance_m(-23.1175, -46.5502, -23.1175, -46.5502) == Decimal("0.00")
    assert (
        Decimal("50") < haversine_distance_m(-23.1175, -46.5502, -23.1170, -46.5500) < Decimal("70")
    )
