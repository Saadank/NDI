import logging

from app.gateways.keycloak_gateway import KeycloakGateway
from app.platform.repositories.user_repository import UserRepository
from app.utils.exceptions import UnauthorizedException, ValidationException

logger = logging.getLogger(__name__)


class AuthenticationService:

    def __init__(self) -> None:
        self.keycloak = KeycloakGateway()
        self.user_repo = UserRepository()

    async def login(self, username: str, password: str) -> dict:
        token_data = self.keycloak.authenticate_user(username, password)

        user_info = self.keycloak.get_user_info_by_token(token_data["access_token"])
        keycloak_id = user_info.get("sub")

        db_user = await self.user_repo.find_by_keycloak_id(keycloak_id)
        if not db_user:
            raise UnauthorizedException("User not registered on the platform")

        if not db_user.get("is_active"):
            raise UnauthorizedException("User account is disabled")

        # Resolve product role for data_sharing
        product_role = None
        from app.platform.repositories.product_repository import ProductRepository
        product_repo = ProductRepository()
        product = await product_repo.find_product_by_slug("data_sharing")
        if product:
            role_record = await product_repo.find_user_product_role(db_user["id"], product["id"])
            if role_record:
                product_role = role_record["role"]

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_in": token_data.get("expires_in"),
            "token_type": "Bearer",
            "user": {
                "id": db_user["id"],
                "email": db_user["email"],
                "first_name": db_user.get("first_name"),
                "last_name": db_user.get("last_name"),
                "tenant_id": db_user["tenant_id"],
                "platform_role": db_user["platform_role"],
                "product_role": product_role,
            },
        }

    async def refresh(self, refresh_token: str) -> dict:
        token_data = self.keycloak.refresh_token(refresh_token)
        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_in": token_data.get("expires_in"),
            "token_type": "Bearer",
        }

    async def logout(self, refresh_token: str) -> bool:
        return self.keycloak.logout_user(refresh_token)


def get_authentication_service() -> AuthenticationService:
    return AuthenticationService()
