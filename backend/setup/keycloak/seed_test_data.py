"""
Seed Test Data Script
Run AFTER setup_realm.py.

Creates:
  - 1 tenant  : Acme Corporation
  - 1 superadmin (org_admin)
  - 1 DPO
  - 3 departments: Finance, Human Resources, IT
  - Per department: 1 data owner + 2 data stewards (requester role)
  - Total: 12 accounts (1 admin + 1 DPO + 3 data owners + 6 stewards + 1 platform admin)

Usage:
    python -X utf8 backend/setup/keycloak/seed_test_data.py
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
SUPER_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD",   "SuperAdmin123!")

PASSWORD = "Test123!"

# ── Tenant ───────────────────────────────────────────────────────────────────
TENANT = {
    "name":        "Acme Corporation",
    "name_ar":     "شركة أكمي",
    "slug":        "acme-corp",
    "tenant_type": "internal_org",
    "dpo_name":    "Nora Al-Rashid",
    "dpo_email":   "nora.dpo@acme.local",
}

# ── Departments ──────────────────────────────────────────────────────────────
DEPARTMENTS = [
    {
        "name": "Finance Department",
        "name_ar": "قسم المالية",
        "slug": "finance",
        "desc": "Financial operations, budgeting, and reporting",
        "data_owner": {
            "email": "ahmed.do@acme.local", "first": "Ahmed", "last": "Al-Farsi",
            "platform_role": "user", "product_role": "data_owner",
        },
        "stewards": [
            {"email": "sara.fin@acme.local",  "first": "Sara",  "last": "Al-Harbi",  "platform_role": "user", "product_role": "requester"},
            {"email": "omar.fin@acme.local",  "first": "Omar",  "last": "Al-Otaibi", "platform_role": "user", "product_role": "requester"},
        ],
    },
    {
        "name": "Human Resources",
        "name_ar": "الموارد البشرية",
        "slug": "hr",
        "desc": "Employee management, recruitment, and HR operations",
        "data_owner": {
            "email": "fatima.do@acme.local", "first": "Fatima", "last": "Al-Qahtani",
            "platform_role": "user", "product_role": "data_owner",
        },
        "stewards": [
            {"email": "khalid.hr@acme.local", "first": "Khalid", "last": "Al-Dosari", "platform_role": "user", "product_role": "requester"},
            {"email": "maha.hr@acme.local",   "first": "Maha",   "last": "Al-Shehri", "platform_role": "user", "product_role": "requester"},
        ],
    },
    {
        "name": "IT Department",
        "name_ar": "قسم تقنية المعلومات",
        "slug": "it",
        "desc": "Technology infrastructure, systems, and security",
        "data_owner": {
            "email": "youssef.do@acme.local", "first": "Youssef", "last": "Al-Zahrani",
            "platform_role": "user", "product_role": "data_owner",
        },
        "stewards": [
            {"email": "layla.it@acme.local",  "first": "Layla",  "last": "Al-Ghamdi", "platform_role": "user", "product_role": "requester"},
            {"email": "faisal.it@acme.local", "first": "Faisal", "last": "Al-Mutairi","platform_role": "user", "product_role": "requester"},
        ],
    },
]

# ── DPO (org-wide) ──────────────────────────────────────────────────────────
DPO_USER = {
    "email": "nora.dpo@acme.local", "first": "Nora", "last": "Al-Rashid",
    "platform_role": "user", "product_role": "dpo",
}

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


def kc_set_attributes(token, user_id, attributes, profile=None):
    payload = {"attributes": attributes}
    if profile:
        payload.update(profile)
    api("PUT", f"/admin/realms/{REALM}/users/{user_id}", payload, token)


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


def create_user(token, tenant_id, u, platform_admin_id=None):
    """Create a user in Keycloak + Postgres + assign product role. Returns DB user ID."""
    api("POST", f"/admin/realms/{REALM}/users", {
        "username":     u["email"],
        "email":        u["email"],
        "enabled":      True,
        "emailVerified": True,
        "firstName":    u["first"],
        "lastName":     u["last"],
        "credentials":  [{"type": "password", "value": PASSWORD, "temporary": False}],
    }, token)

    kc_id = kc_get_user_id(token, u["email"])
    if not kc_id:
        print(f"  ! Could not find {u['email']} in KC")
        return None

    kc_assign_roles(token, kc_id, [u["platform_role"], u["product_role"]])

    sql(f"""
        INSERT INTO t_users (tenant_id, keycloak_id, email, first_name, last_name, platform_role)
        VALUES ({tenant_id}, '{kc_id}', '{u["email"]}', '{u["first"]}', '{u["last"]}', '{u["platform_role"]}')
        ON CONFLICT (keycloak_id) DO NOTHING;
    """)
    db_id = int(sql_value(f"SELECT id FROM t_users WHERE keycloak_id = '{kc_id}';"))

    kc_set_attributes(token, kc_id, {
        "tenant_id": [str(tenant_id)],
        "user_id":   [str(db_id)],
    }, profile={"email": u["email"], "firstName": u["first"], "lastName": u["last"], "emailVerified": True})

    sql(f"""
        INSERT INTO t_user_product_roles (user_id, product_id, role, assigned_by)
        VALUES ({db_id}, 1, '{u["product_role"]}', {db_id})
        ON CONFLICT (user_id, product_id) DO NOTHING;
    """)

    return db_id


# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Seed Test Data — Data Management Platform")
    print("=" * 60)

    token = get_admin_token()
    print("\n[1] KC admin token obtained")

    # ── 1. Create tenant ─────────────────────────────────────────────────────
    t = TENANT
    print(f"\n[2] Creating tenant '{t['name']}'...")
    sql(f"""
        INSERT INTO t_tenants (name, name_ar, slug, tenant_type, dpo_name, dpo_email)
        VALUES ('{t["name"]}', '{t["name_ar"]}', '{t["slug"]}', '{t["tenant_type"]}',
                '{t["dpo_name"]}', '{t["dpo_email"]}')
        ON CONFLICT (slug) DO NOTHING;
    """)
    tenant_id = int(sql_value(f"SELECT id FROM t_tenants WHERE slug = '{t['slug']}';"))
    print(f"  + Tenant ID: {tenant_id}")

    # ── 2. Bootstrap platform admin ──────────────────────────────────────────
    print(f"\n[3] Bootstrapping platform admin...")
    sql(f"""
        INSERT INTO t_platform_admins (email, first_name, last_name)
        VALUES ('{SUPER_EMAIL}', 'Super', 'Admin')
        ON CONFLICT (email) DO NOTHING;
    """)
    pa_id = int(sql_value(f"SELECT id FROM t_platform_admins WHERE email = '{SUPER_EMAIL}';"))

    # ── 3. Wire super admin ─────────────────────────────────────────────────
    print(f"\n[4] Wiring super admin ({SUPER_EMAIL})...")
    kc_super_id = kc_get_user_id(token, SUPER_EMAIL)
    if kc_super_id:
        sql(f"""
            INSERT INTO t_users (tenant_id, keycloak_id, email, first_name, last_name, platform_role)
            VALUES ({tenant_id}, '{kc_super_id}', '{SUPER_EMAIL}', 'Super', 'Admin', 'platform_admin')
            ON CONFLICT (keycloak_id) DO NOTHING;
        """)
        super_db_id = int(sql_value(f"SELECT id FROM t_users WHERE keycloak_id = '{kc_super_id}';"))
        kc_set_attributes(token, kc_super_id, {
            "tenant_id": [str(tenant_id)], "user_id": [str(super_db_id)],
        }, profile={"email": SUPER_EMAIL, "firstName": "Super", "lastName": "Admin", "emailVerified": True})
        sql(f"UPDATE t_platform_admins SET keycloak_id = '{kc_super_id}' WHERE email = '{SUPER_EMAIL}';")
        print(f"  + Super admin DB ID: {super_db_id}")

    # ── 4. Enable products ──────────────────────────────────────────────────
    print(f"\n[5] Enabling products...")
    sql(f"""
        INSERT INTO t_tenant_products (tenant_id, product_id, enabled_by)
        SELECT {tenant_id}, id, {pa_id} FROM t_products WHERE is_active = TRUE
        ON CONFLICT (tenant_id, product_id) DO NOTHING;
    """)

    # ── 5. Create DPO ────────────────────────────────────────────────────────
    print(f"\n[6] Creating DPO...")
    dpo_db_id = create_user(token, tenant_id, DPO_USER)
    print(f"  + {DPO_USER['email']:35s}  DPO  DB={dpo_db_id}")

    # ── 6. Create departments + users ────────────────────────────────────────
    print(f"\n[7] Creating departments and users...")
    super_db_id_str = sql_value(f"SELECT id FROM t_users WHERE email = '{SUPER_EMAIL}';")
    super_db_id = int(super_db_id_str) if super_db_id_str else 1

    for dept in DEPARTMENTS:
        # Create group
        sql(f"""
            INSERT INTO t_groups (tenant_id, name, name_ar, slug, description)
            VALUES ({tenant_id}, '{dept["name"]}', '{dept["name_ar"]}', '{dept["slug"]}', '{dept["desc"]}')
            ON CONFLICT (tenant_id, slug) DO NOTHING;
        """)
        grp_id = int(sql_value(f"SELECT id FROM t_groups WHERE tenant_id = {tenant_id} AND slug = '{dept['slug']}';"))
        print(f"\n  Department: {dept['name']} (ID: {grp_id})")

        # Create data owner
        do = dept["data_owner"]
        do_db_id = create_user(token, tenant_id, do)
        sql(f"UPDATE t_users SET group_id = {grp_id} WHERE id = {do_db_id};")
        sql(f"UPDATE t_groups SET data_owner_id = {do_db_id} WHERE id = {grp_id};")
        print(f"    Data Owner: {do['email']:35s}  DB={do_db_id}")

        # Create stewards
        for st in dept["stewards"]:
            st_db_id = create_user(token, tenant_id, st)
            sql(f"UPDATE t_users SET group_id = {grp_id} WHERE id = {st_db_id};")
            print(f"    Steward:    {st['email']:35s}  DB={st_db_id}")

    # ── 7. Default workflow template ─────────────────────────────────────────
    print(f"\n[8] Creating default workflow template...")
    existing = sql_value(
        f"SELECT COUNT(*) FROM t_workflow_templates WHERE tenant_id = {tenant_id} "
        f"AND sharing_type IS NULL AND data_classification IS NULL;"
    )
    if existing and int(existing) == 0:
        sql(f"""
            INSERT INTO t_workflow_templates (tenant_id, name, sharing_type, data_classification, is_active, created_by)
            VALUES ({tenant_id}, 'Default Approval Workflow', NULL, NULL, TRUE, {super_db_id});
        """)
        tpl_id = sql_value(
            f"SELECT id FROM t_workflow_templates WHERE tenant_id = {tenant_id} "
            f"AND name = 'Default Approval Workflow' ORDER BY created_at DESC LIMIT 1;"
        )
        if tpl_id:
            sql(f"""
                INSERT INTO t_template_steps (template_id, step_order, step_type, name, assignee_role, sla_days)
                VALUES
                    ('{tpl_id}', 1, 'approval', 'DPO Review', 'dpo', 3),
                    ('{tpl_id}', 2, 'approval', 'Data Owner Approval', 'data_owner', 5);
            """)
            print(f"  + Default template: DPO Review -> Data Owner Approval")
    else:
        print(f"  + Already exists, skipping")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SETUP COMPLETE")
    print("=" * 60)
    print(f"\n  Tenant: {TENANT['name']}")
    print(f"\n  {'Email':<38} {'Role':<14} {'Department':<20} Password")
    print(f"  {'-'*38} {'-'*14} {'-'*20} {'-'*10}")
    print(f"  {SUPER_EMAIL:<38} {'admin':<14} {'—':<20} {SUPER_PASSWORD}")
    print(f"  {DPO_USER['email']:<38} {'dpo':<14} {'Org-wide':<20} {PASSWORD}")
    for dept in DEPARTMENTS:
        do = dept["data_owner"]
        print(f"  {do['email']:<38} {'data_owner':<14} {dept['name']:<20} {PASSWORD}")
        for st in dept["stewards"]:
            print(f"  {st['email']:<38} {'steward':<14} {dept['name']:<20} {PASSWORD}")
    print(f"\n  Workflow: DPO Review (3d SLA) -> Data Owner Approval (5d SLA)")
    print(f"\n  Login: POST http://localhost:8000/api/v1/platform/auth/login")
    print()


if __name__ == "__main__":
    main()
