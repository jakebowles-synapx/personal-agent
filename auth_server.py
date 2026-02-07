#!/usr/bin/env python3
"""Minimal OAuth authentication server for Microsoft 365.

This server provides a simple way to authenticate with Microsoft 365 when tokens
are missing or expired beyond refresh. Run this script, complete the OAuth flow
in your browser, and the server will automatically shut down after success.

Usage:
    python auth_server.py            # Opens browser automatically
    python auth_server.py --headless # Prints auth URL for headless/remote use

For headless/remote servers:
1. Set APP_BASE_URL to your ngrok/tunnel URL in .env
2. Run: python auth_server.py --headless
3. Copy the auth URL and open it in a browser on any device
4. Complete the Microsoft login
5. The callback will be handled by the server via ngrok
"""

import argparse
import asyncio
import sys
import webbrowser
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from src.microsoft.auth import MicrosoftAuth

# Default user ID for single-user mode
DEFAULT_USER_ID = "default"

app = FastAPI(title="Microsoft 365 Auth")
auth = MicrosoftAuth()

# Flag to signal shutdown
shutdown_event = asyncio.Event()


@app.get("/")
async def index():
    """Root endpoint - redirect to auth."""
    auth_url = auth.get_auth_url(DEFAULT_USER_ID)
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Microsoft 365 Authentication</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 600px;
                margin: 100px auto;
                padding: 20px;
                text-align: center;
            }}
            .btn {{
                display: inline-block;
                padding: 12px 24px;
                background: #0078d4;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 16px;
            }}
            .btn:hover {{
                background: #106ebe;
            }}
        </style>
    </head>
    <body>
        <h1>Microsoft 365 Authentication</h1>
        <p>Click the button below to sign in with your Microsoft account.</p>
        <p><a href="{auth_url}" class="btn">Sign in with Microsoft</a></p>
    </body>
    </html>
    """)


@app.get("/auth/callback")
async def callback(code: str = None, state: str = None, error: str = None, error_description: str = None):
    """Handle OAuth callback from Microsoft."""
    if error:
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 600px;
                    margin: 100px auto;
                    padding: 20px;
                    text-align: center;
                }}
                .error {{
                    color: #d32f2f;
                    background: #ffebee;
                    padding: 20px;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <h1>Authentication Failed</h1>
            <div class="error">
                <p><strong>Error:</strong> {error}</p>
                <p>{error_description or ''}</p>
            </div>
            <p>Please close this window and try again.</p>
        </body>
        </html>
        """, status_code=400)

    if not code or not state:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error</h1>
            <p>Missing authorization code or state parameter.</p>
        </body>
        </html>
        """, status_code=400)

    try:
        result = await auth.handle_callback(code=code, state=state)

        # Schedule shutdown after sending response
        asyncio.create_task(schedule_shutdown())

        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 600px;
                    margin: 100px auto;
                    padding: 20px;
                    text-align: center;
                }
                .success {
                    color: #2e7d32;
                    background: #e8f5e9;
                    padding: 20px;
                    border-radius: 4px;
                }
            </style>
        </head>
        <body>
            <h1>Authentication Successful!</h1>
            <div class="success">
                <p>You have successfully connected your Microsoft 365 account.</p>
                <p>Your tokens have been securely stored.</p>
            </div>
            <p>You can close this window. The auth server will shut down automatically.</p>
        </body>
        </html>
        """)

    except Exception as e:
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 600px;
                    margin: 100px auto;
                    padding: 20px;
                    text-align: center;
                }}
                .error {{
                    color: #d32f2f;
                    background: #ffebee;
                    padding: 20px;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <h1>Authentication Failed</h1>
            <div class="error">
                <p>{str(e)}</p>
            </div>
            <p>Please close this window and try again.</p>
        </body>
        </html>
        """, status_code=400)


@app.get("/status")
async def status():
    """Check connection status."""
    connected = auth.is_connected(DEFAULT_USER_ID)
    return {
        "connected": connected,
        "user_id": DEFAULT_USER_ID,
        "message": "Connected to Microsoft 365" if connected else "Not connected",
    }


async def schedule_shutdown():
    """Schedule server shutdown after a short delay."""
    await asyncio.sleep(2)  # Give time for response to be sent
    shutdown_event.set()


class Server(uvicorn.Server):
    """Custom server that can be shut down programmatically."""

    async def serve(self, sockets=None):
        """Start server and wait for shutdown signal."""
        config = self.config
        if not config.loaded:
            config.load()

        self.lifespan = config.lifespan_class(config)
        await self.startup(sockets=sockets)

        if self.started:
            # Wait for either shutdown signal or shutdown_event
            shutdown_task = asyncio.create_task(shutdown_event.wait())
            server_task = asyncio.create_task(self.main_loop())

            done, pending = await asyncio.wait(
                [shutdown_task, server_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

        await self.shutdown(sockets=sockets)


def main():
    """Run the auth server."""
    parser = argparse.ArgumentParser(description="Microsoft 365 OAuth authentication server")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Headless mode: print auth URL instead of opening browser (for remote/headless servers)",
    )
    args = parser.parse_args()

    from src.config import settings

    # Check if already connected
    if auth.is_connected(DEFAULT_USER_ID):
        print("Already connected to Microsoft 365!")
        print("To re-authenticate, delete tokens.db and run again.")
        return

    # Get auth URL
    auth_url = auth.get_auth_url(DEFAULT_USER_ID)

    print("Starting Microsoft 365 authentication server...")
    print(f"Server running at: {settings.app_base_url}")
    print(f"Redirect URI: {settings.app_base_url}/auth/callback")

    if args.headless:
        print("\n" + "=" * 60)
        print("HEADLESS MODE - Open this URL in a browser:")
        print("=" * 60)
        print(f"\n{auth_url}\n")
        print("=" * 60)
        print("Waiting for OAuth callback...")
    else:
        print("\nOpening browser for authentication...")
        webbrowser.open(auth_url)

    # Run server
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
    server = Server(config)
    asyncio.run(server.serve())

    print("\nAuthentication complete! Server has shut down.")
    print("You can now use the MCP server tools.")


if __name__ == "__main__":
    main()
