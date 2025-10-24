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

# List of conformsTo URIs to ensure are present on the landing page
CUSTOM_CONFORMS_TO = [
    "https://api.stacspec.org/v1.0.0-rc.2/ogcapi-features/extensions/transaction",
    "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/filter",
    "https://api.stacspec.org/v1.0.0/item-search",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    "https://api.stacspec.org/v1.0.0/ogcapi-features",
    "http://www.opengis.net/spec/cql2/1.0/conf/cql2-text",
    "https://api.stacspec.org/v1.0.0-rc.2/item-search#context",
    "https://api.stacspec.org/v1.0.0-rc.2/item-search#query",
    "https://api.stacspec.org/v1.0.0/collections",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/simpletx",
    "https://api.stacspec.org/v1.0.0-rc.3/item-search#fields",
    "https://api.stacspec.org/v1.0.0/core",
    "https://api.stacspec.org/v1.0.0-rc.2/item-search#sort",
    "https://api.stacspec.org/v1.0.0-rc.2/item-search#filter",
]

# Prepare base URL if provided
clean_base_url = base_url.rstrip('/') if base_url else None

# Middleware to adjust JSON responses: add conformsTo and optionally override base URLs
@app.middleware("http")
async def stac_response_middleware(request: Request, call_next):
    response = await call_next(request)

    # Only process JSON responses
    if response.headers.get("content-type", "").startswith("application/json"):
        # Read the response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        try:
            # Parse JSON content as Python object
            json_data: Any = json.loads(response_body.decode())

            # Determine if this request is for the landing page
            req_path = request.url.path
            is_root = (req_path == "/")
            is_root_with_prefix = (root_path and req_path.rstrip("/") == root_path)

            if isinstance(json_data, dict):
                conforms = json_data.get("conformsTo")
                # If conformsTo exists anywhere (e.g., /conformance), merge our entries
                if isinstance(conforms, list):
                    existing = set(str(u) for u in conforms)
                    for uri in CUSTOM_CONFORMS_TO:
                        if uri not in existing:
                            conforms.append(uri)
                            existing.add(uri)
                # If it's the landing page and conformsTo is missing, add the full list
                elif conforms is None and (is_root or is_root_with_prefix):
                    json_data["conformsTo"] = list(CUSTOM_CONFORMS_TO)
                # else: leave as-is for other responses

            # Dump to string for optional URL rewriting
            json_str = json.dumps(json_data)

            # If BASE_URL override is configured, perform replacements
            if clean_base_url:
                # Comprehensive URL replacement for Kong/Docker environments
                # 1. Handle specific pattern with port 8000
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
                json_str = json_str.replace("http://localhost:8087", clean_base_url)
                json_str = json_str.replace("https://localhost:8087", clean_base_url)
                json_str = json_str.replace("http://localhost:8000", clean_base_url)
                json_str = json_str.replace("https://localhost:8000", clean_base_url)
                # 5. Docker service name replacements (Kong internal routing)
                json_str = json_str.replace("http://stac:8000", clean_base_url)
                json_str = json_str.replace("https://stac:8000", clean_base_url)
                json_str = json_str.replace("http://stac:8087", clean_base_url)
                json_str = json_str.replace("https://stac:8087", clean_base_url)
                # 6. Handle specific domain with port patterns more aggressively
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
