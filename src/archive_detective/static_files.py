"""Static file helpers with dev-friendly cache headers."""

from __future__ import annotations

from starlette.staticfiles import StaticFiles


class NoCacheStaticFiles(StaticFiles):
    """Serve static assets without aggressive browser caching."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["cache-control"] = "no-cache, must-revalidate"
        return response
