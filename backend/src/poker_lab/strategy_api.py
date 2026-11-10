import os

from fastapi import APIRouter, Depends, HTTPException, Request

from poker_lab.strategy_catalog import SolutionCatalog, configured_catalog, strict_json
from poker_lab.strategy_provider import (
    PrecomputedStrategyProvider,
    QueryResult,
    ScenarioIndex,
    SourceRequest,
    SourceView,
    StrategyQuery,
    source_view,
)


def create_strategy_router(catalog: SolutionCatalog | None = None) -> APIRouter:
    registry = (
        catalog if catalog is not None else configured_catalog(os.environ.get("STRATEGY_CATALOG"))
    )
    provider = PrecomputedStrategyProvider(registry)

    async def validate_json(request: Request) -> None:
        if request.method == "POST":
            body = await request.body()
            if len(body) > 2 * 1024 * 1024:
                raise HTTPException(413, "Strategy query exceeds 2 MiB")
            try:
                strict_json(body.decode("utf-8"))
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None

    router = APIRouter(
        prefix="/api/strategy", tags=["strategy"], dependencies=[Depends(validate_json)]
    )

    @router.get("/scenarios", response_model=ScenarioIndex)
    def scenarios() -> ScenarioIndex:
        return provider.scenarios()

    @router.get("/examples", response_model=ScenarioIndex)
    def examples() -> ScenarioIndex:
        return provider.scenarios("synthetic_demo")

    @router.post("/query", response_model=QueryResult)
    def query(body: StrategyQuery) -> QueryResult:
        return provider.query(body)

    @router.post("/frequencies", response_model=QueryResult)
    def frequencies(body: StrategyQuery) -> QueryResult:
        return provider.query(body)

    @router.post("/source", response_model=SourceView)
    def source(body: SourceRequest) -> SourceView:
        entry = registry.source(body.solution_id, body.mode)
        if entry is None:
            raise HTTPException(404, "No publishable source in the requested data mode")
        return source_view(entry)

    return router
