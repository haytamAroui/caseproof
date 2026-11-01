"""Workspace catalog adapter; installed only in the injected loopback composition."""
from typing import Protocol

from fastapi import APIRouter, Header
from pydantic import ValidationError

from application.litigation.workspace_contract import MatterCatalogView
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token


class MatterCatalog(Protocol):
    def list_matters(self, bearer: str) -> list[dict[str, object]]: ...


def create_workspace_catalog_router(catalog: MatterCatalog | None) -> APIRouter:
    router = APIRouter()

    @router.get("/v2/workspace/matters", response_model=MatterCatalogView,
                response_model_by_alias=True)
    def matters(authorization: str | None = Header(default=None)) -> MatterCatalogView:
        bearer = _token(authorization)
        if catalog is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            return MatterCatalogView.model_validate({
                "schema": "caseproof-workspace-matters-v1",
                "matters": catalog.list_matters(bearer),
            })
        except ValidationError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    return router
