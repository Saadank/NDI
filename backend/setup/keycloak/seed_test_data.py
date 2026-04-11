"""
Seed Test Data Script
Creates a test tenant (Acme Corp) with multiple users in different roles.
Run after setup_realm.py.

Usage:
    python -X utf8 backend/setup/keycloak/seed_test_data.py
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse

KC_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
KC_ADMIN_USER = os.getenv("KEYCLOAK_ADMIN_USER", "admin")
KC_ADMIN_PASS = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM = os.getenv("KEYCLOAK_REALM", "datasharing-dev")

# Test users to create
TEST_TENANT = {
    "name": "Acme Corporation",
    "name_ar": "شركة أكمي",
    "slug": "acme-corp",
    "tenant_type": "internal_org",
    "dpo_name": "Fatima Al-Rashid",
    "dpo_email": "fatima@acme.local",
}

TEST_USERS = [
    {"email": "ahmed@acme.local",   "first": "Ahmed",  "last": "Al-Saud",    "platform_role": "org_admin",  "product_role": "requester",  "password": "Test123!"},
    {"email": "fatima@acme.local",  "first": "Fatima", "last": "Al-Rashid",  "platform_role": "org_admin",  "product_role": "dpo",        "password": "Test123!"},
    {"email": "omar@acme.local",    "first": "Omar",   "last": "Hassan",     "platform_role": "org_admin",  "product_role": "data_owner", "password": "Test123!"},
    {"email": "sara@acme.local",    "first": "Sara",   "last": "Ibrahim",    "platform_role": "org_admin",  "product_role": "source",     "password": "Test123!"},
    {"email": "khalid@acme.local",  "first": "Khalid", "last": "Al-Mutairi", "platform_role": "org_admin",  "product_role": "receiver",   "password": "Test123!"},
]

# External partner tenant
PARTNER_TENANT = {
    "name": "Saudi Data Authority",
    "name_ar": "هيئة البيانات السعودية",
    "slug": "sda-gov",
    "tenant_type": "external_org",
    "dpo_name": "Noura Al-Otaibi",
    "dpo_email": "noura@sda.gov.local",
}

PARTNER_USERS = [
    {"email": "noura@sda.gov.local", "first": "Noura", "last": "Al-Otaibi", "platform_role": "org_admin", "product_role": "receiver", "password": "Test123!"},
]


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
        print(f"  ! {method} {path} -> {e.code}: {err_body[:200]}")
        return None


def get_admin_token():
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": KC_ADMIN_USER,
        "password": KC_ADMIN_PASS,
    }).encode()
    req = urllib.request.Request(
        f"{KC_URL}/realms/master/protocol/openid-connect/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["access_token"]


def create_kc_user(token, email, first, last, password, roles):
    """Create user in Keycloak and assign roles. Returns keycloak user ID."""
    api("POST", f"/admin/realms/{REALM}/users", {
        "username": email,
        "email": email,
        "enabled": True,
        "emailVerified": True,
        "firstName": first,
        "lastName": last,
        "credentials": [{"type": "password", "value": password, "temporary": False}],
    }, token)

    users = api("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(email)}&exact=true", token=token)
    if not users:
        print(f"  ! Could not find user {email} after creation")
        return None

    user_id = users[0]["id"]

    for role_name in roles:
        role_rep = api("GET", f"/admin/realms/{REALM}/roles/{role_name}", token=token)
        if role_rep:
            api("POST", f"/admin/realms/{REALM}/users/{user_id}/role-mappings/realm", [role_rep], token)

    return user_id


def run_sql(sql):
    """Execute SQL against the PostgreSQL container."""
    result = subprocess.run(
        ["docker", "exec", "datasharing-1st-postgres-1", "psql", "-U", "dsplatform", "-d", "datasharing_dev", "-c", sql],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ! SQL error: {result.stderr.strip()}")
    return result.stdout


def seed_tenant(tenant_info, users_info, token, tenant_id_expected):
    """Seed a tenant + its users in both Keycloak and PostgreSQL."""
    t = tenant_info
    print(f"\n--- Tenant: {t['name']} ---")

    # Create tenant in DB
    run_sql(f"""
        INSERT INTO t_tenants (name, name_ar, slug, tenant_type, dpo_name, dpo_email)
        VALUES ('{t["name"]}', '{t["name_ar"]}', '{t["slug"]}', '{t["tenant_type"]}', '{t["dpo_name"]}', '{t["dpo_email"]}')
        ON CONFLICT (slug) DO NOTHING;
    """)
    print(f"  + Tenant '{t['name']}' created in DB")

    # Get actual tenant ID
    out = run_sql(f"SELECT id FROM t_tenants WHERE slug = '{t['slug']}';")
    lines = [l.strip() for l in out.strip().split("\n") if l.strip() and l.strip() != "id" and not l.strip().startswith("-") and not l.strip().startswith("(")]
    actual_tenant_id = int(lines[0]) if lines else tenant_id_expected
    print(f"  + Tenant ID: {actual_tenant_id}")

    # Enable all products for tenant
    run_sql(f"""
        INSERT INTO t_tenant_products (tenant_id, product_id, enabled_by)
        SELECT {actual_tenant_id}, id, 1 FROM t_products WHERE is_active = TRUE
        ON CONFLICT (tenant_id, product_id) DO NOTHING;
    """)
    print(f"  + All products enabled for tenant")

    # Create users
    for u in users_info:
        kc_id = create_kc_user(token, u["email"], u["first"], u["last"], u["password"],
                               [u["platform_role"], u["product_role"]])
        if not kc_id:
            continue

        # Set tenant_id attribute in Keycloak
        api("PUT", f"/admin/realms/{REALM}/users/{kc_id}", {
            "attributes": {"tenant_id": [str(actual_tenant_id)]},
        }, token)

        # Create user in DB
        run_sql(f"""
            INSERT INTO t_users (tenant_id, keycloak_id, email, first_name, last_name, platform_role)
            VALUES ({actual_tenant_id}, '{kc_id}', '{u["email"]}', '{u["first"]}', '{u["last"]}', '{u["platform_role"]}')
            ON CONFLICT (keycloak_id) DO NOTHING;
        """)

        # Get user ID and assign product role
        user_out = run_sql(f"SELECT id FROM t_users WHERE keycloak_id = '{kc_id}';")
        user_lines = [l.strip() for l in user_out.strip().split("\n") if l.strip() and l.strip() != "id" and not l.strip().startswith("-") and not l.strip().startswith("(")]
        if user_lines:
            db_user_id = int(user_lines[0])
            # Assign product role for Data Sharing
            run_sql(f"""
                INSERT INTO t_user_product_roles (user_id, product_id, role, assigned_by)
                VALUES ({db_user_id}, 1, '{u["product_role"]}', {db_user_id})
                ON CONFLICT (user_id, product_id) DO NOTHING;
            """)

        print(f"  + User '{u['email']}' ({u['product_role']}) created [KC: {kc_id[:8]}...]")


def main():
    print("=" * 60)
    print("  Seed Test Data — Data Management Platform")
    print("=" * 60)

    token = get_admin_token()
    print("Admin token obtained")

    seed_tenant(TEST_TENANT, TEST_USERS, token, 2)
    seed_tenant(PARTNER_TENANT, PARTNER_USERS, token, 3)

    # Summary
    print("\n" + "=" * 60)
    print("  Seed complete! Test accounts:")
    print("=" * 60)
    print(f"\n  Tenant: {TEST_TENANT['name']}")
    for u in TEST_USERS:
        print(f"    {u['email']:30s} role={u['product_role']:12s} pw={u['password']}")
    print(f"\n  Tenant: {PARTNER_TENANT['name']}")
    for u in PARTNER_USERS:
        print(f"    {u['email']:30s} role={u['product_role']:12s} pw={u['password']}")

    print(f"\n  Test login with any user:")
    print(f'    curl -X POST http://localhost:8000/api/v1/platform/auth/login \\')
    print(f'      -H "Content-Type: application/json" \\')
    print(f'      -d \'{{"username": "ahmed@acme.local", "password": "Test123!"}}\'')
    print()


if __name__ == "__main__":
    main()
