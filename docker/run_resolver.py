"""Validate Compose-provided DNS addresses before starting Unbound."""

import os
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path


def main() -> None:
    address = IPv4Address(os.environ["SSRF_LAB_RESOLVER_IP"])
    subnet = IPv4Network(os.environ["SSRF_LAB_DNS_SUBNET"])
    if address not in subnet:
        raise ValueError("Resolver address must belong to its DNS network")
    template = Path("/etc/unbound/unbound.conf.template").read_text()
    configuration = template.replace("@RESOLVER_IP@", str(address)).replace(
        "@DNS_SUBNET@", str(subnet)
    )
    Path("/tmp/unbound.conf").write_text(configuration)
    os.execvp("unbound", ("unbound", "-d", "-c", "/tmp/unbound.conf"))


if __name__ == "__main__":
    main()
