"""
Seed Second Tenant Data Script
Run AFTER seed_test_data.py (which creates Acme Corp, the first tenant).

Creates:
  - 1 tenant  : Globex Industries
  - 4 accounts: requester, receiver, dpo, dataowner
    All under Globex. Use these to test cross-tenant privilege isolation
    against the Acme Corp accounts.

Usage:
    python -X utf8 backend/setup/keycloak/seed_tenant2_data.py
"""
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

# ── Config (mirrors .env.dev) ────────────────────────────────────────────────
KC_URL         = os.getenv("KEYCLOAK_SERVER_URL",    "http://localhost:8080")
KC_ADMIN_USER  = os.getenv("KEYCLOAK_ADMIN_USER",    "admin")
KC_ADMIN_PASS  = os.getenv("KEYCLOAK_ADMIN_PASSWORD","admin")
REALM          = os.getenv("KEYCLOAK_REALM",         "datasharing-dev")
SUPER_EMAIL    = os.getenv("SUPER_ADMIN_EMAIL",      "superadmin@datasharing.local")

# ── Second tenant ────────────────────────────────────────────────────────────
TENANT = {
    "name":        "Globex Industries",
    "name_ar":     "شركة غلوبكس",
    "slug":        "globex-ind",
    "tenant_type": "internal_org",
    "dpo_name":    "DPO Globex",
    "dpo_email":   "dpo@globex.local",
}

# ── Role-named accounts (same roles, different tenant) ───────────────────────
USERS = [
    {
        "email":         "requester@globex.local",
        "first":         "Requester",
        "last":          "Globex",
        "platform_role": "org_admin",
        "product_role":  "requester",
        "password":      "Test123!",
    },
    {
        "email":         "receiver@globex.local",
        "first":         "Receiver",
        "last":          "Globex",
        "platform_role": "org_admin",
        "product_role":  "receiver",
        "password":      "Test123!",
    },
    {
        "email":         "dpo@globex.local",
        "first":         "DPO",
        "last":          "Globex",
        "platform_role": "org_admin",
        "product_role":  "dpo",
        "password":      "Test123!",
    },
    {
        "email":         "dataowner@globex.local",
        "first":         "DataOwner",
        "last":          "Globex",
        "platform_role": "org_admin",
        "product_role":  "data_owner",
        "password":      "Test123!",
    },
]

# ─────────────────────────────────────────────────────────────────────────────

def api(method, path, data=None, token=""):
    url = f"{KC_URL}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode()
            return json.loads(content) if content else None
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return None
        err_body = e.read().decode() if e.fp else ""
        print(f"  ! KC {method} {path} -> {e.code}: {err_body[:200]}")
        return None


def get_admin_token():
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id":  "admin-cli",
        "username":   KC_ADMIN_USER,
        "password":   KC_ADMIN_PASS,
    }).encode()
    req = urllib.request.Request(
        f"{KC_URL}/realms/master/protocol/openid-connect/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["access_token"]


def kc_get_user_id(token, email):
    users = api("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(email)}&exact=true", token=token)
    return users[0]["id"] if users else None


def kc_assign_roles(token, user_id, role_names):
    for role_name in role_names:
        role_rep = api("GET", f"/admin/realms/{REALM}/roles/{role_name}", token=token)
        if role_rep:
            api("POST", f"/admin/realms/{REALM}/users/{user_id}/role-mappings/realm", [role_rep], token)


def kc_set_attributes(token, user_id, attributes):
    api("PUT", f"/admin/realms/{REALM}/users/{user_id}", {"attributes": attributes}, token)


def sql(query):
    result = subprocess.run(
        ["docker", "exec", "ndi-postgres-1",
         "psql", "-U", "dsplatform", "-d", "datasharing_dev", "-c", query],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ! SQL error: {result.stderr.strip()}")
    return result.stdout


def sql_value(query):
    """Return the single scalar value from a query."""
    out = sql(query)
    lines = [
        l.strip() for l in out.strip().split("\n")
        if l.strip()
        and not l.strip().startswith("-")
        and not l.strip().startswith("(")
        and l.strip() not in ("id", "count")
        and not l.strip().startswith("INSERT")
        and not l.strip().startswith("UPDATE")
    ]
    return lines[0] if lines else None


# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Seed Tenant 2 — Globex Industries")
    print("=" * 60)

    token = get_admin_token()
    print("\n[1] KC admin token obtained")

    # ── 1. Create tenant ──────────────────────────────────────────────────────
    t = TENANT
    print(f"\n[2] Creating tenant '{t['name']}' in DB...")
    sql(f"""
        INSERT INTO t_tenants (name, name_ar, slug, tenant_type, dpo_name, dpo_email)
        VALUES ('{t["name"]}', '{t["name_ar"]}', '{t["slug"]}', '{t["tenant_type"]}',
                '{t["dpo_name"]}', '{t["dpo_email"]}')
        ON CONFLICT (slug) DO NOTHING;
    """)
    tenant_id = int(sql_value(f"SELECT id FROM t_tenants WHERE slug = '{t['slug']}';"))
    print(f"  + Tenant ID: {tenant_id}")

    # ── 2. Look up platform admin (already created by seed_test_data.py) ─────
    print(f"\n[3] Looking up platform admin...")
    platform_admin_id = int(sql_value(
        f"SELECT id FROM t_platform_admins WHERE email = '{SUPER_EMAIL}';"
    ))
    print(f"  + Platform admin DB ID: {platform_admin_id}")

    # ── 3. Enable all products for tenant ─────────────────────────────────────
    print(f"\n[4] Enabling all products for tenant {tenant_id}...")
    sql(f"""
        INSERT INTO t_tenant_products (tenant_id, product_id, enabled_by)
        SELECT {tenant_id}, id, {platform_admin_id} FROM t_products WHERE is_active = TRUE
        ON CONFLICT (tenant_id, product_id) DO NOTHING;
    """)
    print(f"  + All products enabled")

    # ── 4. Create role-named users ─────────────────────────────────────────────
    print(f"\n[5] Creating role-named users...")
    for u in USERS:
        # Keycloak
        api("POST", f"/admin/realms/{REALM}/users", {
            "username":     u["email"],
            "email":        u["email"],
            "enabled":      True,
            "emailVerified": True,
            "firstName":    u["first"],
            "lastName":     u["last"],
            "credentials":  [{"type": "password", "value": u["password"], "temporary": False}],
        }, token)

        kc_id = kc_get_user_id(token, u["email"])
        if not kc_id:
            print(f"  ! Could not find {u['email']} in KC after creation")
            continue

        kc_assign_roles(token, kc_id, [u["platform_role"], u["product_role"]])

        # Postgres
        sql(f"""
            INSERT INTO t_users (tenant_id, keycloak_id, email, first_name, last_name, platform_role)
            VALUES ({tenant_id}, '{kc_id}', '{u["email"]}', '{u["first"]}', '{u["last"]}', '{u["platform_role"]}')
            ON CONFLICT (keycloak_id) DO NOTHING;
        """)
        db_user_id = int(sql_value(f"SELECT id FROM t_users WHERE keycloak_id = '{kc_id}';"))

        # Stamp KC attributes
        kc_set_attributes(token, kc_id, {
            "tenant_id": [str(tenant_id)],
            "user_id":   [str(db_user_id)],
        })

        # Product role (data_sharing product_id = 1)
        sql(f"""
            INSERT INTO t_user_product_roles (user_id, product_id, role, assigned_by)
            VALUES ({db_user_id}, 1, '{u["product_role"]}', {db_user_id})
            ON CONFLICT (user_id, product_id) DO NOTHING;
        """)

        print(f"  + {u['email']:30s}  role={u['product_role']:12s}  KC={kc_id[:8]}...")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Done! Tenant 2 accounts created:")
    print("=" * 60)
    print(f"\n  Tenant : {TENANT['name']}  (slug: {TENANT['slug']})")
    print(f"\n  {'Email':<32} {'Role':<14} Password")
    print(f"  {'-'*32} {'-'*14} {'-'*12}")
    for u in USERS:
        print(f"  {u['email']:<32} {u['product_role']:<14} {u['password']}")
    print(f"\n  Test privilege isolation:")
    print(f"    Login as requester@globex.local and try to access Acme Corp data")
    print(f"    Login as requester@acme.local and try to access Globex data")
    print(f"\n  Login endpoint:")
    print(f"    POST http://localhost:8000/api/v1/platform/auth/login")
    print(f'    {{"username": "requester@globex.local", "password": "Test123!"}}')
    print()


if __name__ == "__main__":
    main()
