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

                # 1. Handle Kong-specific pattern: "http://geoint-api.eodev.thaicom.io:8000/stac/"
                # Replace any external domain with port numbers
                json_str = re.sub(
                    r'http://([^:]+):8000',
                    f'{clean_base_url}',
                    json_str
                )

                # 2. Handle HTTPS version of the same pattern
                json_str = re.sub(
                    r'https://([^:]+):8000',
                    f'{clean_base_url}',
                    json_str
                )

                # 3. Generic port removal for external domains (any port)
                json_str = re.sub(
                    r'http://([^:/]+):\d+',
                    lambda m: f'https://{m.group(1)}' if clean_base_url.startswith('https://') and clean_base_url.split('://')[1] == m.group(1) else clean_base_url,
                    json_str
                )

                # 4. Direct localhost replacements
                json_str = json_str.replace(f"http://localhost:8087", clean_base_url)
                json_str = json_str.replace(f"https://localhost:8087", clean_base_url)
                json_str = json_str.replace(f"http://localhost:8000", clean_base_url)
                json_str = json_str.replace(f"https://localhost:8000", clean_base_url)

                # 5. Docker service name replacements (Kong internal routing)
                json_str = json_str.replace(f"http://stac:8000", clean_base_url)
                json_str = json_str.replace(f"https://stac:8000", clean_base_url)
                json_str = json_str.replace(f"http://stac:8087", clean_base_url)
                json_str = json_str.replace(f"https://stac:8087", clean_base_url)

                # 6. Handle specific domain with port patterns more aggressively
                # This specifically targets the pattern you mentioned
                if "geoint-api.eodev.thaicom.io" in json_str:
                    json_str = json_str.replace("http://geoint-api.eodev.thaicom.io:8000", clean_base_url)
                    json_str = json_str.replace("https://geoint-api.eodev.thaicom.io:8000", clean_base_url)

                # 7. Generic Docker service pattern replacement
                json_str = re.sub(
                    r'https?://[a-zA-Z0-9][a-zA-Z0-9\-_]*[a-zA-Z0-9]*:\d+',
                    clean_base_url,
                    json_str
                )

                # 8. Handle full paths with service names
                if root_path:
                    json_str = re.sub(
                        r'https?://[^/\s"]+:\d+' + re.escape(root_path),
                        f"{clean_base_url}{root_path}",
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
