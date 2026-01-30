#!/usr/bin/env python3
"""
Alpha OTP Generation Script

Generates one-time passwords (OTPs) for alpha access control.
Each OTP can only be used once by one email address.

USAGE:
    python scripts/generate_alpha_otps.py                    # Generate 50 OTPs (default)
    python scripts/generate_alpha_otps.py --count 25         # Generate custom number
    python scripts/generate_alpha_otps.py --dry-run          # Show OTPs without inserting
    python scripts/generate_alpha_otps.py --list             # List existing OTPs and status
    python scripts/generate_alpha_otps.py --stats            # Show OTP usage statistics

OTP SCHEMA:
    {
        "otp_code": "ABC123XYZ",      # Unique 10-character alphanumeric code
        "used": false,                 # Whether the code has been used
        "used_by_email": null,         # Email that used this code (null if unused)
        "used_at": null,               # Timestamp when used (null if unused)
        "created_at": "2024-01-15T..."  # When the code was generated
    }

SECURITY:
    - OTPs are alphanumeric (A-Z, 0-9), no ambiguous characters (0/O, 1/I/L)
    - Codes are 10 characters for readability while maintaining uniqueness
    - Store the output securely - these are your alpha access keys!
"""

import sys
import os
import secrets
import string
from datetime import datetime, timezone

# Add parent directory to path so we can import BackEnd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import alpha_otps_collection, DB_NAME


# Characters to use for OTP generation (no ambiguous characters)
# Excluded: 0, O, 1, I, L to avoid confusion
OTP_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
OTP_LENGTH = 10
DEFAULT_COUNT = 50


def generate_otp_code() -> str:
    """Generate a single OTP code."""
    return ''.join(secrets.choice(OTP_CHARS) for _ in range(OTP_LENGTH))


def generate_otps(count: int, dry_run: bool = False) -> list[dict]:
    """
    Generate OTP codes and insert into database.
    
    Args:
        count: Number of OTPs to generate
        dry_run: If True, only show what would be created (no DB insert)
    
    Returns:
        List of generated OTP documents
    """
    print("=" * 80)
    print("ALPHA OTP GENERATOR")
    print("=" * 80)
    print(f"Database: {DB_NAME}")
    print(f"Count: {count}")
    print(f"Mode: {'DRY RUN (no database changes)' if dry_run else 'LIVE (will insert into database)'}")
    print("=" * 80)
    print()
    
    # Generate unique OTP codes
    otps = []
    generated_codes = set()
    
    # Also check for existing codes in DB to avoid duplicates
    existing_codes = set()
    if not dry_run:
        existing = alpha_otps_collection.find({}, {"otp_code": 1})
        existing_codes = {doc["otp_code"] for doc in existing}
        if existing_codes:
            print(f"⚠️  Found {len(existing_codes)} existing OTPs in database")
    
    now = datetime.now(timezone.utc)
    
    attempts = 0
    max_attempts = count * 10  # Prevent infinite loop
    
    while len(otps) < count and attempts < max_attempts:
        attempts += 1
        code = generate_otp_code()
        
        # Ensure uniqueness (both in this batch and in DB)
        if code in generated_codes or code in existing_codes:
            continue
        
        generated_codes.add(code)
        otps.append({
            "otp_code": code,
            "used": False,
            "used_by_email": None,
            "used_at": None,
            "created_at": now
        })
    
    if len(otps) < count:
        print(f"⚠️  Warning: Could only generate {len(otps)} unique OTPs")
    
    # Insert into database (unless dry run)
    if not dry_run:
        result = alpha_otps_collection.insert_many(otps)
        print(f"✅ Inserted {len(result.inserted_ids)} OTPs into database")
    else:
        print("ℹ️  DRY RUN - No OTPs were inserted")
    
    print()
    print("=" * 80)
    print("GENERATED OTP CODES")
    print("=" * 80)
    print()
    print("Copy these codes and store them securely for distribution to alpha testers:")
    print()
    
    for i, otp in enumerate(otps, 1):
        print(f"  {i:2}. {otp['otp_code']}")
    
    print()
    print("=" * 80)
    
    return otps


def list_otps():
    """List all existing OTPs and their status."""
    print("=" * 80)
    print("EXISTING ALPHA OTPS")
    print("=" * 80)
    print(f"Database: {DB_NAME}")
    print("=" * 80)
    print()
    
    otps = list(alpha_otps_collection.find().sort("created_at", 1))
    
    if not otps:
        print("No OTPs found in database.")
        return
    
    unused = [otp for otp in otps if not otp.get("used")]
    used = [otp for otp in otps if otp.get("used")]
    
    print(f"📊 SUMMARY: {len(otps)} total, {len(unused)} unused, {len(used)} used")
    print()
    
    if unused:
        print("UNUSED OTPS (available for distribution):")
        for otp in unused:
            print(f"  ✅ {otp['otp_code']}")
        print()
    
    if used:
        print("USED OTPS:")
        for otp in used:
            email = otp.get("used_by_email", "unknown")
            used_at = otp.get("used_at", "unknown")
            if hasattr(used_at, 'strftime'):
                used_at = used_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"  ❌ {otp['otp_code']} → {email} ({used_at})")
        print()


def show_stats():
    """Show OTP usage statistics."""
    print("=" * 80)
    print("ALPHA OTP STATISTICS")
    print("=" * 80)
    print(f"Database: {DB_NAME}")
    print("=" * 80)
    print()
    
    total = alpha_otps_collection.count_documents({})
    used = alpha_otps_collection.count_documents({"used": True})
    unused = alpha_otps_collection.count_documents({"used": False})
    
    print(f"  Total OTPs:     {total}")
    print(f"  Used:           {used}")
    print(f"  Available:      {unused}")
    print(f"  Usage rate:     {(used/total*100) if total > 0 else 0:.1f}%")
    print()
    
    if used > 0:
        print("RECENT SIGNUPS:")
        recent = alpha_otps_collection.find({"used": True}).sort("used_at", -1).limit(5)
        for otp in recent:
            email = otp.get("used_by_email", "unknown")
            used_at = otp.get("used_at", "unknown")
            if hasattr(used_at, 'strftime'):
                used_at = used_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"    {email} ({used_at})")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate alpha OTP codes")
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Number of OTPs to generate (default: {DEFAULT_COUNT})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without inserting into database"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_otps",
        help="List existing OTPs and their status"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show OTP usage statistics"
    )
    
    args = parser.parse_args()
    
    try:
        if args.list_otps:
            list_otps()
        elif args.stats:
            show_stats()
        else:
            generate_otps(args.count, dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
