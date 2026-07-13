from fastapi import APIRouter, Request


router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "version": request.app.state.settings.version}
