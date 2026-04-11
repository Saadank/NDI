import logging
from typing import Any

from keycloak import KeycloakAdmin, KeycloakOpenID

from app.core.config import get_settings
from app.utils.exceptions import UnauthorizedException, ValidationException

logger = logging.getLogger(__name__)


class KeycloakGateway:

    def __init__(self) -> None:
        settings = get_settings()
        self.server_url = settings.KEYCLOAK_SERVER_URL
        self.realm_name = settings.KEYCLOAK_REALM
        self.client_id = settings.KEYCLOAK_CLIENT_ID
        self.client_secret = settings.KEYCLOAK_CLIENT_SECRET

        self.keycloak_openid = KeycloakOpenID(
            server_url=self.server_url,
            client_id=self.client_id,
            realm_name=self.realm_name,
            client_secret_key=self.client_secret,
            verify=False,
        )

        self.keycloak_admin = KeycloakAdmin(
            server_url=self.server_url,
            realm_name=self.realm_name,
            client_id=self.client_id,
            client_secret_key=self.client_secret,
            verify=False,
        )
        self._ensure_admin_token()

    # --- Authentication ---

    def authenticate_user(self, username: str, password: str) -> dict[str, Any]:
        try:
            return self.keycloak_openid.token(username, password)
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise ValidationException("Invalid username or password")

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        try:
            return self.keycloak_openid.refresh_token(refresh_token)
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise UnauthorizedException("Invalid refresh token")

    def get_user_info_by_token(self, token: str) -> dict[str, Any]:
        try:
            return self.keycloak_openid.userinfo(token)
        except Exception as e:
            logger.error(f"User info fetch failed: {e}")
            raise UnauthorizedException("Invalid token")

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            return self.keycloak_openid.decode_token(token, validate=True)
        except Exception as e:
            logger.error(f"Token decode failed: {e}")
            raise UnauthorizedException("Invalid token")

    def logout_user(self, refresh_token: str) -> bool:
        try:
            self.keycloak_openid.logout(refresh_token)
            return True
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False

    def get_public_key(self) -> str:
        raw = self.keycloak_openid.public_key()
        return f"-----BEGIN PUBLIC KEY-----\n{raw}\n-----END PUBLIC KEY-----"

    # --- User Management ---

    async def create_user(
        self,
        username: str,
        email: str,
        first_name: str | None,
        last_name: str | None,
        password: str,
        roles: list[str] | None = None,
        groups: list[str] | None = None,
        attributes: dict | None = None,
    ) -> str:
        try:
            user_data: dict[str, Any] = {
                "username": username,
                "email": email,
                "enabled": True,
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            }
            if first_name:
                user_data["firstName"] = first_name
            if last_name:
                user_data["lastName"] = last_name
            if groups:
                user_data["groups"] = groups
            if attributes:
                user_data["attributes"] = attributes

            user_id = self.keycloak_admin.create_user(payload=user_data, exist_ok=False)
            if roles:
                self._assign_realm_roles(user_id, roles)
            return user_id
        except Exception as e:
            logger.error(f"User creation failed: {e}")
            raise Exception("Failed to create user in Keycloak")

    def get_user_by_username(self, username: str) -> dict | None:
        try:
            users = self.keycloak_admin.get_users(query={"username": username, "exact": True})
            return users[0] if users else None
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            raise

    async def get_user_roles(self, user_id: str) -> list[str]:
        try:
            roles = await self.keycloak_admin.a_get_realm_roles_of_user(user_id)
            return [r["name"] for r in roles]
        except Exception as e:
            logger.error(f"Failed to get user roles: {e}")
            raise

    def get_user_groups(self, user_id: str) -> list[dict]:
        try:
            return self.keycloak_admin.get_user_groups(user_id)
        except Exception as e:
            logger.error(f"Failed to get user groups: {e}")
            raise

    def upsert_user_attributes(self, user_id: str, payload: dict) -> None:
        try:
            user_data = self.keycloak_admin.get_user(user_id=user_id)
            current_attrs = user_data.get("attributes", {})
            user_data["attributes"] = {**current_attrs, **payload}
            self.keycloak_admin.update_user(user_id=user_id, payload=user_data)
        except Exception as e:
            logger.error(f"Attribute update failed: {e}")
            raise

    def disable_user(self, user_id: str) -> None:
        try:
            self.keycloak_admin.disable_user(user_id=user_id)
        except Exception as e:
            logger.error(f"User disable failed: {e}")
            raise

    def enable_user(self, user_id: str) -> None:
        try:
            self.keycloak_admin.enable_user(user_id=user_id)
        except Exception as e:
            logger.error(f"User enable failed: {e}")
            raise

    # --- Group Management ---

    def create_group(self, group_name: str) -> str:
        try:
            return self.keycloak_admin.create_group(payload={"name": group_name})
        except Exception as e:
            logger.error(f"Group creation failed: {e}")
            raise

    def add_user_to_group(self, user_id: str, group_id: str) -> None:
        try:
            self.keycloak_admin.group_user_add(user_id=user_id, group_id=group_id)
        except Exception as e:
            logger.error(f"Add user to group failed: {e}")
            raise

    def get_group_by_path(self, path: str) -> dict:
        try:
            return self.keycloak_admin.get_group_by_path(path)
        except Exception as e:
            logger.error(f"Get group failed: {e}")
            raise

    def delete_group(self, group_id: str) -> None:
        try:
            self.keycloak_admin.delete_group(group_id)
        except Exception as e:
            logger.error(f"Group deletion failed: {e}")
            raise

    # --- Internal ---

    def _ensure_admin_token(self) -> None:
        try:
            token = self.keycloak_admin.connection.token
            if not token:
                self.keycloak_admin.connection.get_token()
        except Exception as e:
            logger.error(f"Admin auth failed: {e}")
            raise

    def _assign_realm_roles(self, user_id: str, roles: list[str]) -> None:
        try:
            realm_roles = self.keycloak_admin.get_realm_roles()
            to_assign = [r for r in realm_roles if r["name"] in roles]
            if to_assign:
                self.keycloak_admin.assign_realm_roles(user_id, to_assign)
        except Exception as e:
            logger.error(f"Role assignment failed: {e}")
            raise
