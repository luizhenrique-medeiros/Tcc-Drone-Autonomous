"""Read-only serial-port discovery for assisted gateway configuration."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SerialPortInfo:
    device: str
    description: str | None
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    vid: int | None
    pid: int | None


def list_serial_ports() -> list[SerialPortInfo]:
    """Enumerate ports without opening them or sending any bytes."""
    try:
        from serial.tools import list_ports
    except ImportError as exc:  # pragma: no cover - dependency error is environment-specific
        raise RuntimeError("pyserial não está instalado") from exc

    return [
        SerialPortInfo(
            device=port.device,
            description=port.description or None,
            manufacturer=port.manufacturer or None,
            product=port.product or None,
            serial_number=port.serial_number or None,
            vid=port.vid,
            pid=port.pid,
        )
        for port in sorted(list_ports.comports(), key=lambda item: item.device.casefold())
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Lista portas seriais disponíveis sem abri-las.")
    parser.add_argument("--json", action="store_true", help="Emite uma lista JSON.")
    args = parser.parse_args()
    ports = list_serial_ports()
    if args.json:
        print(json.dumps([asdict(port) for port in ports], ensure_ascii=False, indent=2))
        return
    if not ports:
        print("Nenhuma porta serial encontrada.")
        return
    for port in ports:
        label = port.description or "sem descrição"
        hardware = (
            f" VID:PID={port.vid:04X}:{port.pid:04X}"
            if port.vid is not None and port.pid is not None
            else ""
        )
        print(f"{port.device} - {label}{hardware}")


if __name__ == "__main__":
    main()
