"""
Keycloak Realm Setup Script
Creates the datasharing-dev realm, client, roles, and seed admin user.
Run once after first docker compose up.

Usage:
    python backend/setup/keycloak/setup_realm.py
"""
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

# Config — matches .env.dev
KC_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
KC_ADMIN_USER = os.getenv("KEYCLOAK_ADMIN_USER", "admin")
KC_ADMIN_PASS = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM = os.getenv("KEYCLOAK_REALM", "datasharing-dev")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "datasharing-backend")
CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "dev-client-secret")
SEED_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "superadmin@datasharing.local")
SEED_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD", "SuperAdmin123!")

ROLES = [
    "platform_admin",
    "org_admin",
    "requester",
    "data_owner",
    "dpo",
    "source",
    "receiver",
]


def api(method: str, path: str, data: dict | None = None, token: str = "") -> dict | list | None:
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
        err_body = e.read().decode() if e.fp else ""
        if e.code == 409:
            print(f"  ⚠ Already exists (409): {path}")
            return None
        print(f"  ✗ {method} {path} → {e.code}: {err_body[:200]}")
        raise


def get_admin_token() -> str:
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials" if False else "password",
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


def main():
    print("=" * 60)
    print("  Keycloak Realm Setup — Data Management Platform")
    print("=" * 60)

    # 1. Get admin token
    print("\n[1/6] Getting admin token...")
    token = get_admin_token()
    print("  ✓ Admin token obtained")

    # 2. Create realm
    print(f"\n[2/6] Creating realm '{REALM}'...")
    try:
        api("POST", "/admin/realms", {
            "realm": REALM,
            "enabled": True,
            "displayName": "Data Management Platform (Dev)",
            "sslRequired": "none",
            "registrationAllowed": False,
            "loginWithEmailAllowed": True,
            "duplicateEmailsAllowed": False,
            "resetPasswordAllowed": True,
            "editUsernameAllowed": False,
            "bruteForceProtected": True,
            "permanentLockout": False,
            "maxFailureWaitSeconds": 900,
            "minimumQuickLoginWaitSeconds": 60,
            "waitIncrementSeconds": 60,
            "quickLoginCheckMilliSeconds": 1000,
            "maxDeltaTimeSeconds": 43200,
            "failureFactor": 5,
            "accessTokenLifespan": 28800,  # 8 hours
            "ssoSessionIdleTimeout": 28800,
            "ssoSessionMaxLifespan": 86400,
        }, token)
        print(f"  ✓ Realm '{REALM}' created")
    except urllib.error.HTTPError:
        print(f"  ⚠ Realm may already exist, continuing...")

    # 3. Create client
    print(f"\n[3/6] Creating client '{CLIENT_ID}'...")
    try:
        api("POST", f"/admin/realms/{REALM}/clients", {
            "clientId": CLIENT_ID,
            "name": "Data Management Platform Backend",
            "enabled": True,
            "clientAuthenticatorType": "client-secret",
            "secret": CLIENT_SECRET,
            "publicClient": False,
            "serviceAccountsEnabled": True,
            "directAccessGrantsEnabled": True,
            "standardFlowEnabled": True,
            "implicitFlowEnabled": False,
            "redirectUris": ["http://localhost:3000/*", "http://localhost:8000/*"],
            "webOrigins": ["http://localhost:3000", "http://localhost:8000"],
            "protocol": "openid-connect",
            "attributes": {
                "access.token.lifespan": "28800",
            },
            "protocolMappers": [
                {
                    "name": "tenant_id",
                    "protocol": "openid-connect",
                    "protocolMapper": "oidc-usermodel-attribute-mapper",
                    "config": {
                        "user.attribute": "tenant_id",
                        "claim.name": "tenant_id",
                        "jsonType.label": "int",
                        "id.token.claim": "true",
                        "access.token.claim": "true",
                        "userinfo.token.claim": "true",
                    },
                },
                {
                    "name": "user_id",
                    "protocol": "openid-connect",
                    "protocolMapper": "oidc-usermodel-attribute-mapper",
                    "config": {
                        "user.attribute": "user_id",
                        "claim.name": "user_id",
                        "jsonType.label": "int",
                        "id.token.claim": "true",
                        "access.token.claim": "true",
                        "userinfo.token.claim": "true",
                    },
                },
            ],
        }, token)
        print(f"  ✓ Client '{CLIENT_ID}' created")
    except urllib.error.HTTPError:
        print(f"  ⚠ Client may already exist, continuing...")

    # 4. Create realm roles
    print(f"\n[4/6] Creating realm roles...")
    for role in ROLES:
        try:
            api("POST", f"/admin/realms/{REALM}/roles", {
                "name": role,
                "description": f"Platform role: {role}",
            }, token)
            print(f"  ✓ Role '{role}' created")
        except urllib.error.HTTPError:
            pass

    # 5. Create seed super admin user
    print(f"\n[5/6] Creating seed admin user '{SEED_EMAIL}'...")
    try:
        api("POST", f"/admin/realms/{REALM}/users", {
            "username": SEED_EMAIL,
            "email": SEED_EMAIL,
            "enabled": True,
            "emailVerified": True,
            "firstName": "Super",
            "lastName": "Admin",
            "attributes": {
                "tenant_id": ["1"],
                "user_id": ["1"],
            },
            "credentials": [{
                "type": "password",
                "value": SEED_PASSWORD,
                "temporary": False,
            }],
        }, token)
        print(f"  ✓ User '{SEED_EMAIL}' created")
    except urllib.error.HTTPError:
        print(f"  ⚠ User may already exist, continuing...")

    # 6. Assign platform_admin role to seed user
    print(f"\n[6/6] Assigning 'platform_admin' role to seed user...")
    try:
        # Get user ID
        users = api("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(SEED_EMAIL)}&exact=true", token=token)
        if users:
            user_id = users[0]["id"]
            # Ensure profile fields are set
            api("PUT", f"/admin/realms/{REALM}/users/{user_id}", {
                "email": SEED_EMAIL, "firstName": "Super", "lastName": "Admin",
                "enabled": True, "emailVerified": True,
            }, token)
            # Get role representation
            role_rep = api("GET", f"/admin/realms/{REALM}/roles/platform_admin", token=token)
            if role_rep:
                api("POST", f"/admin/realms/{REALM}/users/{user_id}/role-mappings/realm", [role_rep], token)
                print(f"  ✓ Role 'platform_admin' assigned to '{SEED_EMAIL}'")
        else:
            print("  ⚠ Could not find seed user to assign role")
    except urllib.error.HTTPError as e:
        print(f"  ⚠ Role assignment error: {e}")

    # 7. Grant realm-management roles to datasharing-backend service account
    # so the backend can create/manage users, assign roles, etc. via admin API.
    print(f"\n[7/7] Granting realm-management roles to '{CLIENT_ID}' service account...")
    try:
        clients = api("GET", f"/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(CLIENT_ID)}", token=token)
        backend_client_uuid = clients[0]["id"] if clients else None

        rm_clients = api("GET", f"/admin/realms/{REALM}/clients?clientId=realm-management", token=token)
        rm_client_uuid = rm_clients[0]["id"] if rm_clients else None

        if not backend_client_uuid or not rm_client_uuid:
            print("  ⚠ Could not resolve service account or realm-management client")
        else:
            sa_user = api("GET", f"/admin/realms/{REALM}/clients/{backend_client_uuid}/service-account-user", token=token)
            sa_user_id = sa_user["id"]

            all_rm_roles = api("GET", f"/admin/realms/{REALM}/clients/{rm_client_uuid}/roles", token=token) or []
            needed = {"manage-users", "view-users", "query-users", "query-groups", "query-clients", "manage-clients", "view-clients", "manage-realm", "view-realm"}
            to_assign = [r for r in all_rm_roles if r["name"] in needed]

            if to_assign:
                api("POST", f"/admin/realms/{REALM}/users/{sa_user_id}/role-mappings/clients/{rm_client_uuid}", to_assign, token)
                print(f"  ✓ Granted {len(to_assign)} realm-management roles to service account")
            else:
                print("  ⚠ No matching realm-management roles found")
    except urllib.error.HTTPError as e:
        print(f"  ⚠ Service account role grant error: {e}")

    print("\n" + "=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print(f"\n  Keycloak Admin:  {KC_URL}  (admin / admin)")
    print(f"  Realm:           {REALM}")
    print(f"  Client:          {CLIENT_ID}")
    print(f"  Client Secret:   {CLIENT_SECRET}")
    print(f"  Seed User:       {SEED_EMAIL} / {SEED_PASSWORD}")
    print(f"\n  Test login:")
    print(f"    POST http://localhost:8000/api/v1/platform/auth/login")
    print(f'    {{"username": "{SEED_EMAIL}", "password": "{SEED_PASSWORD}"}}')
    print()


if __name__ == "__main__":
    main()
