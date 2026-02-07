"""Azure AD OAuth flow with MSAL."""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from msal import ConfidentialClientApplication

from src.config import settings

logger = logging.getLogger(__name__)

# Microsoft Graph scopes for delegated permissions
SCOPES = [
    "User.Read",
    "Mail.Read",
    "Calendars.Read",
    "Chat.Read",
    "Files.Read.All",
    "Sites.Read.All",  # For SharePoint and Copilot Retrieval API
    "OnlineMeetings.Read",
    "OnlineMeetingTranscript.Read.All",  # For meeting transcripts
    "OnlineMeetingAiInsight.Read.All",  # For Copilot AI insights (requires Copilot license)
]


class TokenStore:
    """Encrypted SQLite storage for OAuth tokens."""

    def __init__(self, db_path: str = "tokens.db"):
        self.db_path = db_path
        self._init_encryption()
        self._init_db()

    def _init_encryption(self) -> None:
        """Initialize Fernet encryption using app secret key."""
        # Derive a valid Fernet key from the app secret
        key = settings.app_secret_key.encode()
        # Pad or truncate to 32 bytes, then base64 encode
        import base64
        key_bytes = key[:32].ljust(32, b"\0")
        self.fernet = Fernet(base64.urlsafe_b64encode(key_bytes))

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                user_id TEXT PRIMARY KEY,
                encrypted_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def save_tokens(self, user_id: str, token_data: dict) -> None:
        """Save encrypted tokens for a user."""
        encrypted = self.fernet.encrypt(json.dumps(token_data).encode()).decode()
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tokens (user_id, encrypted_data, created_at, updated_at)
            VALUES (?, ?, COALESCE((SELECT created_at FROM tokens WHERE user_id = ?), ?), ?)
        """, (user_id, encrypted, user_id, now, now))
        conn.commit()
        conn.close()
        logger.info(f"Saved tokens for user {user_id}")

    def get_tokens(self, user_id: str) -> dict | None:
        """Get decrypted tokens for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT encrypted_data FROM tokens WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        try:
            decrypted = self.fernet.decrypt(row[0].encode()).decode()
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt tokens for user {user_id}: {e}")
            return None

    def delete_tokens(self, user_id: str) -> None:
        """Delete tokens for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tokens WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Deleted tokens for user {user_id}")

    def has_tokens(self, user_id: str) -> bool:
        """Check if a user has stored tokens."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM tokens WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists


class MicrosoftAuth:
    """Handles Microsoft OAuth authentication."""

    def __init__(self, db_path: str = "tokens.db") -> None:
        self.client_id = settings.azure_client_id
        self.client_secret = settings.azure_client_secret
        self.tenant_id = settings.azure_tenant_id
        self.redirect_uri = f"{settings.app_base_url}/auth/callback"

        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority,
        )

        self.token_store = TokenStore(db_path=db_path)
        self._pending_states: dict[str, str] = {}  # state -> user_id mapping

    def get_auth_url(self, user_id: str) -> str:
        """Generate the OAuth authorization URL."""
        import secrets
        state = secrets.token_urlsafe(32)
        self._pending_states[state] = user_id

        auth_url = self.app.get_authorization_request_url(
            scopes=SCOPES,
            state=state,
            redirect_uri=self.redirect_uri,
        )
        logger.info(f"Generated auth URL for user {user_id}")
        return auth_url

    async def handle_callback(self, code: str, state: str) -> dict:
        """Handle the OAuth callback and exchange code for tokens."""
        # Validate state
        user_id = self._pending_states.pop(state, None)
        if not user_id:
            raise ValueError("Invalid or expired state parameter")

        # Exchange code for tokens
        result = self.app.acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
        )

        if "error" in result:
            error_msg = result.get("error_description", result.get("error"))
            logger.error(f"Token exchange failed for user {user_id}: {error_msg}")
            raise ValueError(f"Authentication failed: {error_msg}")

        # Store tokens
        token_data = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=result["expires_in"])).isoformat(),
            "scope": result.get("scope", ""),
        }
        self.token_store.save_tokens(user_id, token_data)

        logger.info(f"Successfully authenticated user {user_id}")
        return {"user_id": user_id, "success": True}

    async def get_access_token(self, user_id: str) -> str | None:
        """Get a valid access token for a user, refreshing if needed."""
        token_data = self.token_store.get_tokens(user_id)
        if not token_data:
            logger.warning(f"No tokens found for user {user_id}")
            return None

        # Check if token is expired (with 5 min buffer)
        expires_at = datetime.fromisoformat(token_data["expires_at"]).replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) + timedelta(minutes=5) >= expires_at:
            # Token expired or expiring soon, refresh it
            logger.info(f"Refreshing token for user {user_id}")
            token_data = await self._refresh_token(user_id, token_data)
            if not token_data:
                return None

        return token_data["access_token"]

    async def _refresh_token(self, user_id: str, token_data: dict) -> dict | None:
        """Refresh an expired access token."""
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            logger.error(f"No refresh token available for user {user_id}")
            self.token_store.delete_tokens(user_id)
            return None

        result = self.app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=SCOPES,
        )

        if "error" in result:
            error_msg = result.get("error_description", result.get("error"))
            logger.error(f"Token refresh failed for user {user_id}: {error_msg}")
            self.token_store.delete_tokens(user_id)
            return None

        # Update stored tokens
        new_token_data = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token", refresh_token),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=result["expires_in"])).isoformat(),
            "scope": result.get("scope", ""),
        }
        self.token_store.save_tokens(user_id, new_token_data)

        return new_token_data

    def is_connected(self, user_id: str) -> bool:
        """Check if a user has connected their Microsoft account."""
        return self.token_store.has_tokens(user_id)

    def disconnect(self, user_id: str) -> None:
        """Disconnect a user's Microsoft account."""
        self.token_store.delete_tokens(user_id)
        logger.info(f"Disconnected Microsoft account for user {user_id}")
