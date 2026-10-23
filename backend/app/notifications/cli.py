"""Operator commands for notifications.

    python -m app.notifications.cli generate-vapid    # a key pair for VAPID_* in .env.prod
"""

import argparse
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_vapid() -> tuple[str, str]:
    """(public, private) keys in the form browsers and pywebpush take: the
    public key as the uncompressed P-256 point and the private key as the raw
    32-byte scalar, both base64url.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    private = key.private_numbers().private_value.to_bytes(32, "big")
    return _b64url(public), _b64url(private)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.notifications.cli")
    parser.add_subparsers(dest="command", required=True).add_parser("generate-vapid", help="print a VAPID key pair")
    parser.parse_args()
    public, private = generate_vapid()
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")
    print("VAPID_SUBJECT=mailto:you@example.com  # a contact the push services can reach")


if __name__ == "__main__":
    main()
