from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class FetchImapEmailsProvider(ToolProvider):
    
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            required_fields = [
                "config_name",
                "email_account",
                "email_password",
                "imap_server",
                "imap_port",
                "recent_count",
            ]
            for field in required_fields:
                if field not in credentials or not credentials[field]:
                    raise ToolProviderCredentialValidationError(f"Missing or empty credential: {field}")
            # 简单格式校验
            if "@" not in credentials["email_account"]:
                raise ToolProviderCredentialValidationError("Invalid email account format")
            # Dify 表单可能会把 number 以 str 形式传进来，统一转成 int 再校验
            try:
                imap_port = int(credentials["imap_port"])
            except Exception:
                raise ToolProviderCredentialValidationError("IMAP port must be a positive integer")
            if imap_port <= 0:
                raise ToolProviderCredentialValidationError("IMAP port must be a positive integer")

            try:
                recent_count = int(credentials["recent_count"])
            except Exception:
                raise ToolProviderCredentialValidationError("Recent email count must be a positive integer")
            if recent_count <= 0:
                raise ToolProviderCredentialValidationError("Recent email count must be a positive integer")
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))

    #########################################################################################
    # If OAuth is supported, uncomment the following functions.
    # Warning: please make sure that the sdk version is 0.4.2 or higher.
    #########################################################################################
    # def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
    #     """
    #     Generate the authorization URL for fetch_imap_emails OAuth.
    #     """
    #     try:
    #         """
    #         IMPLEMENT YOUR AUTHORIZATION URL GENERATION HERE
    #         """
    #     except Exception as e:
    #         raise ToolProviderOAuthError(str(e))
    #     return ""
        
    # def _oauth_get_credentials(
    #     self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    # ) -> Mapping[str, Any]:
    #     """
    #     Exchange code for access_token.
    #     """
    #     try:
    #         """
    #         IMPLEMENT YOUR CREDENTIALS EXCHANGE HERE
    #         """
    #     except Exception as e:
    #         raise ToolProviderOAuthError(str(e))
    #     return dict()

    # def _oauth_refresh_credentials(
    #     self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    # ) -> OAuthCredentials:
    #     """
    #     Refresh the credentials
    #     """
    #     return OAuthCredentials(credentials=credentials, expires_at=-1)
