"""Loopback workspace password adapter for the existing pinned development Auth.

No cookies, refresh-token transport, session database, signup or admin capability.
"""
from __future__ import annotations

import http.client
import threading
import time
from typing import Protocol

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from apps.api.access_control import AccessFailure, AccessRejected, IdentityServiceUnavailable, InvalidBearer
from apps.api.litigation_evidence_app import _token
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin

PROJECT = 'ldwmocpxwskvhoojndrd'


class LoginBody(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)


class SessionView(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    access_token: str = Field(min_length=1, max_length=8192, repr=False)
    expires_at: int = Field(gt=0)


class WorkspaceAuth(Protocol):
    def login(self, body: LoginBody) -> SessionView: ...
    def logout(self, bearer: str) -> None: ...


class SupabaseWorkspaceAuth:
    def __init__(self, key: str):
        self.key = key
        self.signin = SupabasePasswordSignin(PROJECT, key)
        self.verifier = SupabaseAuthUserVerifier(PROJECT, HttpsSupabaseUserLookup(PROJECT, key))

    def login(self, body: LoginBody) -> SessionView:
        try:
            session = self.signin.sign_in(PasswordCredentials(body.email, body.password.get_secret_value()))
            verified = self.verifier.verify_bearer(session.access_token)
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return SessionView(access_token=session.access_token, expires_at=int(verified.expires_at.timestamp()))

    def logout(self, bearer: str) -> None:
        con = http.client.HTTPSConnection(PROJECT + '.supabase.co', timeout=10)
        try:
            con.request('POST', '/auth/v1/logout?scope=local', headers={
                'apikey': self.key, 'Authorization': 'Bearer ' + bearer,
                'Content-Type': 'application/json',
            })
            result = con.getresponse()
            status = result.status
            result.read(65537)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status not in (200, 204, 401, 403):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)


def create_workspace_auth_router(auth: WorkspaceAuth | None) -> APIRouter:
    router = APIRouter()
    # Loopback-only aggregate limiter: bounded memory, no email/IP retention.
    attempts: list[float] = []
    lock = threading.Lock()

    def origin_guard(request: Request) -> None:
        origin = request.headers.get('origin')
        # Browser writes must come from the serving origin. CLI callers omit Origin.
        if origin is not None and origin != str(request.base_url).rstrip('/'):
            raise AccessRejected(AccessFailure.PERMISSION_DENIED)
        if request.headers.get('sec-fetch-site') in ('cross-site', 'none'):
            raise AccessRejected(AccessFailure.PERMISSION_DENIED)
        if auth is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)

    @router.post('/v2/workspace/session', response_model=SessionView)
    async def login(request: Request) -> SessionView:
        origin_guard(request)
        with lock:
            now = time.monotonic()
            attempts[:] = [t for t in attempts if t > now - 60]
            if len(attempts) >= 12:
                raise HTTPException(429, 'Too many sign-in attempts', headers={'Retry-After': '60'})
            attempts.append(now)
        # Bound raw input before parsing; never echo validation input/password.
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 8192:
                raise HTTPException(413, 'Sign-in request too large')
        try:
            body = LoginBody.model_validate_json(raw)
        except ValueError:
            raise HTTPException(422, 'Invalid sign-in request') from None
        assert auth is not None
        # Run blocking upstream HTTPS outside the ASGI event loop.
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(auth.login, body)

    @router.post('/v2/workspace/session/end', status_code=204)
    def logout(request: Request, authorization: str | None = Header(default=None)) -> Response:
        origin_guard(request)
        assert auth is not None
        auth.logout(_token(authorization))
        return Response(status_code=204)

    return router
