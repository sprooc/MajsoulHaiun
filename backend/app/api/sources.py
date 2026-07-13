from fastapi import APIRouter, Query, Request

from app.sources.base import GameMode, GamePage, RemotePlayer


router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/players/search", response_model=list[RemotePlayer], response_model_by_alias=True)
async def search_players(
    request: Request,
    source: str,
    q: str = Query(min_length=1, max_length=100),
    mode: GameMode = Query(),
    limit: int = Query(20, ge=1, le=50),
) -> list[RemotePlayer]:
    return await request.app.state.source_registry.get(source).search_players(q, mode, limit)


@router.get("/players/{source}/{player_id}/games", response_model=GamePage, response_model_by_alias=True)
async def list_player_games(
    request: Request,
    source: str,
    player_id: str,
    mode: GameMode = Query(),
    cursor: int | None = Query(None, ge=0),
    limit: int = Query(20, ge=1, le=50),
) -> GamePage:
    return await request.app.state.source_registry.get(source).list_games(player_id, mode, cursor, limit)
