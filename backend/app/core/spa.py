"""Serve a built SPA without turning missing API or asset paths into HTML."""
from pathlib import PurePosixPath

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        if any(part.startswith(".") for part in PurePosixPath(path).parts if part != "."):
            raise HTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            first = path.lstrip("/").split("/", 1)[0]
            if (
                exc.status_code != 404
                or scope["method"] not in {"GET", "HEAD"}
                or first in {"api", "assets", "health", "ready"}
                or PurePosixPath(path).suffix
            ):
                raise
            return await super().get_response("index.html", scope)
