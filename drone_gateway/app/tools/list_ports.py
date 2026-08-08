"""CLI entry point for read-only serial-port discovery."""

from app.mavlink.ports import SerialPortInfo, list_serial_ports, main

__all__ = ["SerialPortInfo", "list_serial_ports", "main"]


if __name__ == "__main__":
    main()
