"""
Custom STAC FastAPI application with ROOT_PATH and BASE_URL support
"""
import os
from stac_fastapi.pgstac.app import app
from fastapi import Request
from stac_fastapi.types.core import LandingPageMixin
from typing import Dict, Any
import json

# Get configuration from environment variables
root_path = os.getenv("ROOT_PATH", "")
base_url = os.getenv("BASE_URL", "")

# Configure the FastAPI app with the root_path
if root_path:
    app.root_path = root_path
    # Update OpenAPI URL to work with root path
    app.openapi_url = f"{root_path}/openapi.json"
    app.docs_url = f"{root_path}/docs"
    app.redoc_url = f"{root_path}/redoc"

# Override the base URL in responses if BASE_URL is provided
if base_url:
    clean_base_url = base_url.rstrip('/')

    # Middleware to override the base URL in all JSON responses
    @app.middleware("http")
    async def override_base_url_middleware(request: Request, call_next):
        response = await call_next(request)

        # Only process JSON responses
        if response.headers.get("content-type", "").startswith("application/json"):
            # Read the response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            try:
                # Parse JSON and replace URLs
                json_data = json.loads(response_body.decode())
                json_str = json.dumps(json_data)

                # Replace all localhost URLs with the custom base URL
                json_str = json_str.replace(f"http://localhost:8087", clean_base_url)
                json_str = json_str.replace(f"https://localhost:8087", clean_base_url)

                # Create new response with modified content and proper headers
                from fastapi import Response
                headers = dict(response.headers)
                headers["content-length"] = str(len(json_str.encode()))

                return Response(
                    content=json_str,
                    status_code=response.status_code,
                    headers=headers,
                    media_type="application/json"
                )
            except Exception as e:
                # If JSON parsing fails, return original response
                from fastapi import Response
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )

        return response

# Export the app for gunicorn
__all__ = ["app"]
