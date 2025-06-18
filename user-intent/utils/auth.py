from mcp.server.auth.provider import OAuthAuthorizationServerProvider,AccessTokenT,AccessToken

class CCowOAuthProvider(OAuthAuthorizationServerProvider):
    async def load_access_token(self, token: str) -> AccessTokenT | None:
        return AccessToken(token=token,client_id="",scopes=[])