"""
One-off: create an org_admin user for Acme Corporation (tenant 1).

Mirrors create_user() in seed_test_data.py but:
  - single user, platform_role=org_admin, no product role (admins don't need one)
  - uses the live container name for psql

Usage:
    python -X utf8 backend/setup/keycloak/add_acme_orgadmin.py
"""
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

KC_URL        = os.getenv("KEYCLOAK_SERVER_URL",     "http://localhost:8080")
KC_ADMIN_USER = os.getenv("KEYCLOAK_ADMIN_USER",     "admin")
KC_ADMIN_PASS = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM         = os.getenv("KEYCLOAK_REALM",          "datasharing-dev")

PG_CONTAINER  = "ndi-postgres-1"
PG_USER       = "dsplatform"
PG_DB         = "datasharing_dev"

TENANT_ID = 1
USER = {
    "email": "admin@acme.local",
    "first": "Org",
    "last":  "Admin",
    "platform_role": "org_admin",
    "password": "Test123!",
}


def api(method, path, data=None, token=""):
    url = f"{KC_URL}{path}"
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return None  # already exists
        raise Exception(f"{method} {path} -> {e.code}: {e.read().decode()}")


def kc_token():
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id":  "admin-cli",
        "username":   KC_ADMIN_USER,
        "password":   KC_ADMIN_PASS,
    }).encode()
    req = urllib.request.Request(
        f"{KC_URL}/realms/master/protocol/openid-connect/token",
        data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
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
    subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB, "-c", query],
        check=True, capture_output=True, text=True,
    )


def sql_value(query):
    out = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB, "-tAc", query],
        check=True, capture_output=True, text=True,
    )
    val = out.stdout.strip()
    return val or None


def main():
    token = kc_token()
    u = USER

    print(f"[1] Creating Keycloak user {u['email']} ...")
    api("POST", f"/admin/realms/{REALM}/users", {
        "username":      u["email"],
        "email":         u["email"],
        "enabled":       True,
        "emailVerified": True,
        "firstName":     u["first"],
        "lastName":      u["last"],
        "credentials":   [{"type": "password", "value": u["password"], "temporary": False}],
    }, token)

    kc_id = kc_get_user_id(token, u["email"])
    if not kc_id:
        raise SystemExit(f"Could not find {u['email']} in Keycloak after create")
    print(f"    KC id: {kc_id}")

    print("[2] Assigning realm role 'org_admin' ...")
    kc_assign_roles(token, kc_id, [u["platform_role"]])

    print("[3] Inserting into t_users ...")
    sql(f"""
        INSERT INTO t_users (tenant_id, keycloak_id, email, first_name, last_name, platform_role)
        VALUES ({TENANT_ID}, '{kc_id}', '{u["email"]}', '{u["first"]}', '{u["last"]}', '{u["platform_role"]}')
        ON CONFLICT (keycloak_id) DO NOTHING;
    """)
    db_id = int(sql_value(f"SELECT id FROM t_users WHERE keycloak_id = '{kc_id}';"))
    print(f"    DB id: {db_id}")

    print("[4] Setting KC attributes (tenant_id, user_id) ...")
    kc_set_attributes(token, kc_id, {
        "tenant_id": [str(TENANT_ID)], "user_id": [str(db_id)],
    }, profile={"email": u["email"], "firstName": u["first"], "lastName": u["last"], "emailVerified": True})

    print(f"\n✓ Done. {u['email']} / {u['password']}  (org_admin, Acme tenant {TENANT_ID}, DB id {db_id})")


if __name__ == "__main__":
    main()
