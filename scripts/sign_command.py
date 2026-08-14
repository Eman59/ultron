#!/usr/bin/env python3
"""
Ultron Command Signer

Signs commands with your private key before sending them to Ultron.
Without a valid signature, Ultron refuses all privileged operations.

Usage:
  python scripts/sign_command.py --key configs/keys/ultron_owner.key \
    --command "self_modify" --target "meta_learning" --param reason="optimize"

  # Or use as a library:
  from scripts.sign_command import OwnerSigner
  signer = OwnerSigner("configs/keys/ultron_owner.key")
  signed = signer.sign("shutdown", "system")
"""

import argparse
import json
import time
import os
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("Install: pip install cryptography")
    sys.exit(1)


class OwnerSigner:
    """Signs commands with the owner's Ed25519 private key."""

    def __init__(self, private_key_path: str):
        key_pem = Path(private_key_path).read_bytes()
        self._private_key = serialization.load_pem_private_key(key_pem, password=None)
        
        # Derive public key for verification
        self._public_key = self._private_key.public_key()
        self._pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def sign(self, command: str, target: str, params: dict = None) -> dict:
        """
        Sign a command. Returns the full signed command object
        ready to send to Ultron's API.
        """
        import secrets

        signed_cmd = {
            "command": command,
            "target": target,
            "params": params or {},
            "timestamp": int(time.time()),
            "nonce": secrets.token_hex(16),
        }

        # Sign the command (without the signature field)
        msg_bytes = json.dumps(signed_cmd, sort_keys=True).encode()
        signature = self._private_key.sign(msg_bytes)

        signed_cmd["signature"] = signature.hex()

        return signed_cmd

    def verify(self, signed_cmd: dict) -> bool:
        """Verify a signed command (for testing)."""
        sig_hex = signed_cmd.pop("signature", "")
        msg_bytes = json.dumps(signed_cmd, sort_keys=True).encode()
        sig_bytes = bytes.fromhex(sig_hex)

        try:
            self._public_key.verify(sig_bytes, msg_bytes)
            signed_cmd["signature"] = sig_hex
            return True
        except Exception:
            signed_cmd["signature"] = sig_hex
            return False

    @property
    def public_key_hex(self) -> str:
        return self._pub_bytes.hex()


def main():
    parser = argparse.ArgumentParser(description="Sign a command for Ultron")
    parser.add_argument("--key", required=True, help="Path to ultron_owner.key")
    parser.add_argument("--command", required=True, help="Command name (e.g., self_modify, shutdown)")
    parser.add_argument("--target", default="system", help="Target of the command")
    parser.add_argument("--param", action="append", default=[], help="Key=value params (repeatable)")
    parser.add_argument("--send", action="store_true", help="Send to Ultron API after signing")
    parser.add_argument("--api", default="http://localhost:8000", help="Ultron API URL")
    args = parser.parse_args()

    # Parse params
    params = {}
    for p in args.param:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k] = v

    # Sign
    signer = OwnerSigner(args.key)
    signed = signer.sign(args.command, args.target, params)

    print(json.dumps(signed, indent=2))

    # Verify locally
    verified = signer.verify(dict(signed))
    print(f"\nLocal verification: {'✓ VALID' if verified else '✗ INVALID'}")

    # Send if requested
    if args.send:
        import urllib.request
        url = f"{args.api}/owner/command"
        req_data = json.dumps(signed).encode()
        req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req)
            print(f"\nSent to Ultron: {resp.status}")
            print(resp.read().decode())
        except Exception as e:
            print(f"\nFailed to send: {e}")


if __name__ == "__main__":
    main()
