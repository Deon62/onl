"""Admin command line.

Give a Supabase Auth user access to the dashboard (create the user first in Supabase -> Authentication):

    uv run python -m app.cli grant --email you@oryne.network --role super_admin
    uv run python -m app.cli grant --email owner@acme.co.ke --role merchant_owner --merchant ORY-M001

The user's id is looked up in Supabase's auth.users table (Postgres only). Pass --user-id to skip the lookup.
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select, text

from app.db import SessionLocal
from app.models import Merchant, Profile
from app.models.enums import ADMIN_ROLES, Role


async def grant(email: str, role: Role, merchant_code: str | None, user_id: str | None, name: str) -> None:
    async with SessionLocal() as session:
        if user_id:
            uid = uuid.UUID(user_id)
        else:
            row = (await session.execute(text("SELECT id FROM auth.users WHERE lower(email) = lower(:e)"), {"e": email})).first()
            if row is None:
                sys.exit(f"No Supabase user with email {email}. Create it in Supabase -> Authentication -> Users first.")
            uid = row[0]

        merchant_id = None
        if role not in ADMIN_ROLES:
            if not merchant_code:
                sys.exit("--merchant is required for merchant roles")
            merchant = (await session.execute(select(Merchant).where(Merchant.code == merchant_code))).scalar_one_or_none()
            if merchant is None:
                sys.exit(f"No merchant with code {merchant_code}")
            merchant_id = merchant.id

        profile = await session.get(Profile, uid)
        if profile is None:
            profile = Profile(user_id=uid, email=email.lower())
            session.add(profile)
        profile.role = role
        profile.merchant_id = merchant_id
        profile.full_name = name or profile.full_name
        await session.commit()
        print(f"Granted {role.value} to {email} ({uid}){' for ' + merchant_code if merchant_code else ''}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grant", help="Give a Supabase user a dashboard role")
    g.add_argument("--email", required=True)
    g.add_argument("--role", required=True, choices=[r.value for r in Role])
    g.add_argument("--merchant", help="Merchant code (e.g. ORY-M001) for merchant roles")
    g.add_argument("--user-id", help="Supabase auth user id (skips the auth.users lookup)")
    g.add_argument("--name", default="")
    args = parser.parse_args()
    if args.cmd == "grant":
        asyncio.run(grant(args.email, Role(args.role), args.merchant, args.user_id, args.name))


if __name__ == "__main__":
    main()
