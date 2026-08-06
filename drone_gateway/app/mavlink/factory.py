from app.core.config import MavlinkMode, Settings
from app.mavlink.fake_gateway import FakeVehicleGateway
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway
from app.mavlink.vehicle_gateway import VehicleGateway


def build_vehicle_gateway(settings: Settings) -> VehicleGateway:
    if settings.mavlink_mode is MavlinkMode.SIMULATION:
        return FakeVehicleGateway(settings)
    return PymavlinkVehicleGateway(settings)
