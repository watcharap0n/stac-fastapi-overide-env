"""
Custom STAC FastAPI application with ROOT_PATH and BASE_URL support
"""
import os
from stac_fastapi.pgstac.app import app
from fastapi import Request
from stac_fastapi.types.core import LandingPageMixin
from typing import Dict, Any
import json
import re

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
                # Parse JSON content
                json_data = json.loads(response_body.decode())
                json_str = json.dumps(json_data)

                # Comprehensive URL replacement for Kong/Docker environments

                # 1. Direct localhost replacements
                json_str = json_str.replace(f"http://localhost:8087", clean_base_url)
                json_str = json_str.replace(f"https://localhost:8087", clean_base_url)
                json_str = json_str.replace(f"http://localhost:8000", clean_base_url)
                json_str = json_str.replace(f"https://localhost:8000", clean_base_url)

                # 2. Docker service name replacements (Kong internal routing)
                json_str = json_str.replace(f"http://stac:8000", clean_base_url)
                json_str = json_str.replace(f"https://stac:8000", clean_base_url)
                json_str = json_str.replace(f"http://stac:8087", clean_base_url)
                json_str = json_str.replace(f"https://stac:8087", clean_base_url)

                # 3. Generic Docker service pattern replacement
                # This catches any http://[service-name]:[port] pattern
                json_str = re.sub(
                    r'https?://[a-zA-Z0-9][a-zA-Z0-9\-_]*[a-zA-Z0-9]*:\d+',
                    clean_base_url,
                    json_str
                )

                # 4. Handle full paths with service names
                if root_path:
                    # Replace patterns like "http://stac:8000/stac/" with proper base URL + path
                    json_str = re.sub(
                        r'https?://[a-zA-Z0-9][a-zA-Z0-9\-_]*[a-zA-Z0-9]*:\d+' + re.escape(root_path),
                        f"{clean_base_url}{root_path}",
                        json_str
                    )

                # 5. Fallback: replace any remaining internal Docker network references
                # This is more aggressive and catches edge cases
                json_str = re.sub(
                    r'https?://[^/\s"]+:\d+',
                    clean_base_url,
                    json_str
                )

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
                print(f"JSON parsing error in middleware: {e}")
                from fastapi import Response
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )

        return response

# Export the app for gunicorn
__all__ = ["app"]
