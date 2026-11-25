from pathlib import Path

import pytest

from app.core import sitl_isolation


@pytest.mark.parametrize(
    ("extra", "flags", "cap_bnd", "no_new_privs", "route", "expected"),
    [
        (None, "0x0", "0", "1", "", True),
        ("gre0", "0x80", "0", "1", "", True),
        ("gre0", "0x81", "0", "1", "", False),
        ("gre0", "0x80", "1000", "1", "", False),
        ("gre0", "0x80", "0", "0", "", False),
        ("gre0", "0x80", "0", "1", "gre0 00000000", False),
        ("eth0", "0x0", "0", "1", "", False),
    ],
)
def test_loopback_container_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: str | None,
    flags: str,
    cap_bnd: str,
    no_new_privs: str,
    route: str,
    expected: bool,
) -> None:
    (tmp_path / ".dockerenv").touch()
    (tmp_path / "status").write_text(
        f"CapInh:\t0\nCapPrm:\t0\nCapEff:\t0\nCapBnd:\t{cap_bnd}\n"
        f"CapAmb:\t0\nNoNewPrivs:\t{no_new_privs}\n"
    )
    (tmp_path / "route").write_text(f"Iface\n{route}")
    interfaces = [(1, "lo")]
    if extra:
        interfaces.append((2, extra))
        (tmp_path / extra).mkdir()
        (tmp_path / extra / "flags").write_text(flags)
    monkeypatch.setattr(sitl_isolation, "_CONTAINER_MARKER", tmp_path / ".dockerenv")
    monkeypatch.setattr(sitl_isolation, "_NETWORK_DEVICES", tmp_path)
    monkeypatch.setattr(sitl_isolation, "_PROCESS_STATUS", tmp_path / "status")
    monkeypatch.setattr(sitl_isolation, "_NETWORK_ROUTES", tmp_path)
    monkeypatch.setattr(sitl_isolation.socket, "if_nameindex", lambda: interfaces)
    assert sitl_isolation.is_loopback_only_container() is expected
