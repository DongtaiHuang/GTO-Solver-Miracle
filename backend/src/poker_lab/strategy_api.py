import os
from collections.abc import Iterator
from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, HTTPException, Request

from poker_lab import exploit, multistreet, training
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

    capacity = BoundedSemaphore(2)

    @router.get("/training/exercises")
    def exercises() -> list[training.Prompt]:
        return training.exercises(registry)

    def training_capacity() -> Iterator[None]:
        if not capacity.acquire(blocking=False):
            raise HTTPException(429, "Training calculation capacity reached")
        try:
            yield
        finally:
            capacity.release()

    @router.post("/training/grade", dependencies=[Depends(training_capacity)])
    def grade(body: training.Submission) -> training.Feedback:
        return training.grade(registry, body)

    @router.post("/training/report", dependencies=[Depends(training_capacity)])
    def report(body: training.Archive) -> training.VerifiedArchive:
        try:
            metrics = training.summarize(body)
            for attempt in body.attempts:
                training.verify_attempt(registry, attempt)
            return training.VerifiedArchive(archive=body, report=metrics)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @router.post("/multistreet-policy")
    def policy_rows(body: multistreet.Context) -> dict[str, dict[str, dict[str, float]]]:
        try:
            return multistreet.policy_rows(body, registry)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @router.post("/multistreet")
    def multistreet_response(body: multistreet.Request) -> multistreet.Analysis:
        if not capacity.acquire(blocking=False):
            raise HTTPException(429, "Response calculation capacity reached")
        try:
            return multistreet.analyze(body, registry)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        finally:
            capacity.release()

    @router.post("/exploit")
    def best_response(body: exploit.Request) -> exploit.Analysis:
        try:
            return exploit.analyze(body, registry)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

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
