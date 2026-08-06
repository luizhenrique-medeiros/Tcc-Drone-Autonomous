class GatewayError(Exception):
    """Base error with a stable code for operational reporting."""

    code = "GATEWAY_ERROR"


class ConfigurationError(GatewayError):
    code = "GATEWAY_CONFIGURATION_INVALID"


class BackendContractError(GatewayError):
    code = "BACKEND_CONTRACT_ERROR"


class BackendUnavailableError(GatewayError):
    code = "BACKEND_UNAVAILABLE"


class VehicleConnectionError(GatewayError):
    code = "VEHICLE_CONNECTION_ERROR"


class VehicleTimeoutError(GatewayError):
    code = "VEHICLE_TIMEOUT"


class MissionValidationError(GatewayError):
    code = "MISSION_VALIDATION_FAILED"


class MissionUploadError(GatewayError):
    code = "MISSION_UPLOAD_FAILED"


class UnsafeOperationError(GatewayError):
    code = "UNSAFE_OPERATION_BLOCKED"
