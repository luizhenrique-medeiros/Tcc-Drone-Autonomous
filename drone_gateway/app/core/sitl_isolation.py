import socket
from pathlib import Path

# Linux can instantiate these fallback tunnel interfaces in a fresh network namespace.
_FALLBACK_TUNNELS = {
    "erspan0",
    "gre0",
    "gretap0",
    "ip6_vti0",
    "ip6gre0",
    "ip6tnl0",
    "ip_vti0",
    "sit0",
    "tunl0",
}
_CONTAINER_MARKER = Path("/.dockerenv")
_NETWORK_DEVICES = Path("/sys/class/net")
_PROCESS_STATUS = Path("/proc/self/status")
_NETWORK_ROUTES = Path("/proc/net")


def is_loopback_only_container() -> bool:
    """Allow loopback and inert kernel tunnels in a container without capabilities."""
    if not _CONTAINER_MARKER.is_file():
        return False
    try:
        names = {name for _, name in socket.if_nameindex()}
        if names == {"lo"}:
            return True
        tunnels = names - {"lo"}
        if "lo" not in names or not tunnels <= _FALLBACK_TUNNELS:
            return False
        status = dict(
            line.split(":\t", 1)
            for line in _PROCESS_STATUS.read_text().splitlines()
            if ":\t" in line
        )
        capabilities = ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")
        if any(int(status[field], 16) for field in capabilities):
            return False
        if status["NoNewPrivs"].strip() != "1":
            return False
        if any(
            int((_NETWORK_DEVICES / tunnel / "flags").read_text(), 16) & 1  # IFF_UP
            for tunnel in tunnels
        ):
            return False
        ipv4 = (_NETWORK_ROUTES / "route").read_text().splitlines()[1:]
        ipv6_path = _NETWORK_ROUTES / "ipv6_route"
        ipv6 = ipv6_path.read_text().splitlines() if ipv6_path.exists() else []
        return all(row.split()[0] == "lo" for row in ipv4) and all(
            row.split()[-1] == "lo" for row in ipv6
        )
    except (OSError, ValueError, KeyError, IndexError):
        return False
