import logging
from uuid import UUID

from app.products.data_sharing.permissions import can_manage_connections, require
from app.products.data_sharing.repositories.connection_repository import ConnectionRepository
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)


class ConnectionService:

    def __init__(self) -> None:
        self.repo = ConnectionRepository()

    async def create_connection(self, data: dict, auth_user: AuthUser) -> dict:
        require(can_manage_connections(auth_user), "Only admins can manage connections")
        return await self.repo.create(
            tenant_id=auth_user.tenant_id,
            db_type=data["db_type"],
            host=data["host"],
            port=data["port"],
            database=data.get("database"),
            username=data["username"],
            password_encrypted=data["password"],  # TODO: encrypt before storing
            description=data.get("description"),
            created_by=auth_user.user_id,
        )

    async def list_connections(self, auth_user: AuthUser) -> list[dict]:
        require(can_manage_connections(auth_user), "Only admins can manage connections")
        return await self.repo.find_by_tenant(auth_user.tenant_id)

    async def get_connection(self, connection_id: UUID, auth_user: AuthUser) -> dict:
        require(can_manage_connections(auth_user), "Only admins can manage connections")
        return await self.repo.find_by_id(connection_id, auth_user.tenant_id)

    async def delete_connection(self, connection_id: UUID, auth_user: AuthUser) -> None:
        require(can_manage_connections(auth_user), "Only admins can manage connections")
        await self.repo.soft_delete(connection_id)

    async def test_connection(self, connection_id: UUID, auth_user: AuthUser) -> dict:
        require(can_manage_connections(auth_user), "Only admins can manage connections")
        conn = await self.repo.find_by_id(connection_id, auth_user.tenant_id)
        # Basic connectivity test using DatabasesOperations pattern
        try:
            from app.gateways.db_connector_gateway import DbConnectorGateway
            gateway = DbConnectorGateway(
                db_type=conn["db_type"], username=conn["username"],
                password=conn["password_encrypted"], host=conn["host"],
                port=str(conn["port"]), database=conn.get("database", ""),
            )
            result = await gateway.test_connection()
            await gateway.close()
            return {"success": result.success, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}


def get_connection_service() -> ConnectionService:
    return ConnectionService()
