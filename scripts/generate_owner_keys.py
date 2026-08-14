#!/usr/bin/env python3
"""
Ultron Owner Key Generator

Generates the Ed25519 key pair that proves YOU are the owner.
Run this ONCE. Store the private key securely. Lose it = lose Ultron.

Output:
  - ultron_owner.key     (PRIVATE — never share, never commit to git)
  - ultron_owner.pub     (PUBLIC  — embedded in the Ultron binary)
  - genesis_block.json   (Ownership manifest — signed proof of creation)

Usage:
  python scripts/generate_owner_keys.py --owner "Imran Sayyed"
"""

import argparse
import json
import hashlib
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


def generate_owner_keys(owner_name: str, output_dir: str = "."):
    """Generate the owner key pair and genesis block."""
    
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    
    print("=" * 55)
    print("  ULTRON OWNER KEY GENERATION")
    print("=" * 55)
    print(f"  Owner: {owner_name}")
    print(f"  Output: {output.absolute()}")
    print()
    
    # Generate Ed25519 key pair
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Serialize private key (PEM format, no password — use HSM in production)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    
    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    
    # Raw public key bytes (for embedding in binary)
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    
    # Create genesis block
    genesis = {
        "version": "1.0",
        "owner": owner_name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "created_timestamp": int(time.time()),
        "public_key_hex": public_raw.hex(),
        "public_key_hash": hashlib.sha256(public_raw).hexdigest(),
        "algorithm": "Ed25519",
        "purpose": "Ultron cryptographic ownership — only this key can control the system",
    }
    
    # Sign the genesis block itself
    genesis_bytes = json.dumps(genesis, sort_keys=True).encode()
    genesis_signature = private_key.sign(genesis_bytes)
    genesis["signature"] = genesis_signature.hex()
    
    # Write files
    private_path = output / "ultron_owner.key"
    public_path = output / "ultron_owner.pub"
    genesis_path = output / "genesis_block.json"
    
    private_path.write_bytes(private_pem)
    os.chmod(private_path, 0o600)  # Owner-only read/write
    
    public_path.write_bytes(public_pem)
    genesis_path.write_text(json.dumps(genesis, indent=2))
    
    # Also write raw public key for Go embedding
    raw_pub_path = output / "owner_pubkey.hex"
    raw_pub_path.write_text(public_raw.hex())
    
    print("  ✓ Private key: ultron_owner.key (KEEP SECRET)")
    print("  ✓ Public key:  ultron_owner.pub")
    print("  ✓ Genesis:     genesis_block.json")
    print("  ✓ Raw pubkey:  owner_pubkey.hex")
    print()
    print(f"  Public Key Hash: {genesis['public_key_hash'][:16]}...")
    print()
    print("  ⚠  STORE ultron_owner.key IN A SECURE LOCATION")
    print("  ⚠  LOSING THIS KEY = PERMANENT LOSS OF CONTROL")
    print("=" * 55)
    
    return genesis


def sign_command(private_key_path: str, command: dict) -> str:
    """Sign a command with the owner's private key."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    
    key_pem = Path(private_key_path).read_bytes()
    private_key = serialization.load_pem_private_key(key_pem, password=None)
    
    command_bytes = json.dumps(command, sort_keys=True).encode()
    signature = private_key.sign(command_bytes)
    
    return signature.hex()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Ultron owner keys")
    parser.add_argument("--owner", required=True, help="Owner name (e.g., 'Imran Sayyed')")
    parser.add_argument("--output", default="./configs/keys", help="Output directory")
    args = parser.parse_args()
    
    generate_owner_keys(args.owner, args.output)
