"""
JWT Authentication Middleware for Django Channels WebSockets.
Extracts JWT token from query string parameter '?token=<jwt_access_token>'.
"""
import logging
from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

logger = logging.getLogger('apps.devices.middleware')
User = get_user_model()


@database_sync_to_async
def get_user_from_jwt(token_str: str):
    try:
        access_token = AccessToken(token_str)  # type: ignore[arg-type]
        user_id = access_token.get('user_id')
        if not user_id:
            logger.warning("No user_id in JWT token: %s", access_token)
            return AnonymousUser()
        user = User.objects.get(id=user_id)
        if not user.is_active:
            logger.warning("User %s is inactive", user_id)
            return AnonymousUser()
        return user
    except Exception as exc:
        logger.warning("JWT decode error in WebSocket auth: %s", exc)
        return AnonymousUser()



class JwtAuthMiddleware:
    """
    Custom WebSocket middleware that authenticates users via JWT in the query string.
    Example: ws://localhost:8000/ws/devices/?token=<access_token>
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if token:
            scope['user'] = await get_user_from_jwt(token)
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)

def JwtAuthMiddlewareStack(inner):
    return JwtAuthMiddleware(inner)
