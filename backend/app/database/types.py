from __future__ import annotations

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import UserDefinedType


class GeographyPoint(UserDefinedType[str]):
    """PostGIS geography point, represented as EWKT at the Python boundary."""

    cache_ok = True

    def get_col_spec(self, **_: object) -> str:
        return "geography(POINT,4326)"


@compiles(GeographyPoint, "sqlite")
def compile_sqlite_geography(_type: GeographyPoint, _compiler: object, **_: object) -> str:
    return "TEXT"


def point_ewkt(latitude: float, longitude: float) -> str:
    return f"SRID=4326;POINT({longitude:.8f} {latitude:.8f})"
