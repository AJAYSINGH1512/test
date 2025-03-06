import asyncio
import concurrent.futures
import os
import time
from typing import Annotated, Callable, List
from datetime import datetime
from transformers import pipeline
import structlog
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException

from llm_guard import scan_output, scan_prompt
from llm_guard.input_scanners.base import Scanner as InputScanner
from llm_guard.output_scanners.base import Scanner as OutputScanner
from llm_guard.vault import Vault
from app.services.state_management import load_state, save_state, generate_unique_job_id

from .config import Config, get_config
# from .otel import configure_otel, instrument_app
from .scanner import (
    get_input_scanners,
    get_output_scanners,
    # scanners_valid_counter,
)
from .schemas import (
    AnalyzeOutputRequest,
    AnalyzeOutputResponse,
    AnalyzePromptRequest,
    AnalyzePromptResponse
)
from .util import configure_logger
from .version import __version__

LOGGER = structlog.getLogger(__name__)


def create_app() -> FastAPI:
    config_file = os.getenv("CONFIG_FILE", "./config/scanners.yml")
    if not config_file:
        raise ValueError("Config file is required")

    config = get_config(config_file)
    log_level = config.app.log_level
    is_debug = log_level == "DEBUG"
    configure_logger(log_level, config.app.log_json)

    vault = Vault()
    input_scanners_func = _get_input_scanners_function(config, vault)
    output_scanners_func = _get_output_scanners_function(config, vault)

    if config.app.scan_fail_fast:
        LOGGER.debug("Scan fail_fast mode is enabled")

    app = FastAPI(
        title=config.app.name,
        description="API to run LLM Guard scanners.",
        debug=is_debug,
        version=__version__
    )

    register_routes(app, config, input_scanners_func, output_scanners_func)

    return app

def _get_input_scanners_function(config: Config, vault: Vault) -> Callable:
    scanners = []
    if not config.app.lazy_load:
        LOGGER.debug("Loading input scanners")
        scanners = get_input_scanners(config.input_scanners, vault)

    def get_cached_scanners() -> List[InputScanner]:
        nonlocal scanners

        if not scanners and config.app.lazy_load:
            LOGGER.debug("Lazy loading input scanners")
            scanners = get_input_scanners(config.input_scanners, vault)

        return scanners

    return get_cached_scanners


def _get_output_scanners_function(config: Config, vault: Vault) -> Callable:
    scanners = []
    if not config.app.lazy_load:
        LOGGER.debug("Loading output scanners")
        scanners = get_output_scanners(config.output_scanners, vault)

    def get_cached_scanners() -> List[OutputScanner]:
        nonlocal scanners

        if not scanners and config.app.lazy_load:
            LOGGER.debug("Lazy loading output scanners")
            scanners = get_output_scanners(config.output_scanners, vault)

        return scanners

    return get_cached_scanners


def register_routes(
    app: FastAPI,
    config: Config,
    input_scanners_func: Callable,
    output_scanners_func: Callable,
):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    limiter = Limiter(key_func=get_remote_address, default_limits=[config.rate_limit.limit])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    if bool(config.rate_limit.enabled):
        app.add_middleware(SlowAPIMiddleware)

    @app.get("/healthz", tags=["Health"])
    @limiter.exempt
    async def read_healthcheck():
        return JSONResponse({"status": "alive"})

    @app.get("/readyz", tags=["Health"])
    @limiter.exempt
    async def read_liveliness():
        return JSONResponse({"status": "ready"})

    @app.post(
        "/analyze/output",
        tags=["Analyze"],
        response_model=AnalyzeOutputResponse,
        status_code=status.HTTP_200_OK,
        description="Analyze an output and return the sanitized output and the results of the scanners",
    )
    async def submit_analyze_output(
        request: AnalyzeOutputRequest,
        # _: Annotated[bool, Depends(check_auth)],
        output_scanners: List[OutputScanner] = Depends(output_scanners_func),
    ) -> AnalyzeOutputResponse:
        state = load_state()
        current_state = state[request.job_id] if request.job_id in state.keys() else {}
        original_prompt = current_state["original_prompt"] if "original_prompt" in current_state.keys() else ""
        LOGGER.debug(
            "Received analyze output request",
            request_prompt=original_prompt,
            request_output=request.output,
        )
        if request.scanners_suppress is not None and len(request.scanners_suppress) > 0:
            LOGGER.debug("Suppressing scanners", scanners=request.scanners_suppress)
            output_scanners = [
                scanner
                for scanner in output_scanners
                if type(scanner).__name__ not in request.scanners_suppress
            ]

        with concurrent.futures.ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            try:
                start_time = time.time()
                sanitized_output, results_valid, results_score = await asyncio.wait_for(
                    loop.run_in_executor(
                        executor,
                        scan_output,
                        output_scanners,
                        original_prompt,
                        request.output,
                        request.only_json
                    ),
                    timeout=config.app.scan_output_timeout,
                )

                # for scanner, valid in results_valid.items():
                #     scanners_valid_counter.add(
                #         1, {"source": "output", "valid": valid, "scanner": scanner}
                #     )

                response = AnalyzeOutputResponse(
                    sanitized_output=sanitized_output,
                    is_valid=all(results_valid.values()),
                    scanners=results_score,
                )
                elapsed_time = time.time() - start_time
                LOGGER.debug(
                    "Sanitized response",
                    scores=results_score,
                    elapsed_time_seconds=round(elapsed_time, 6),
                )
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Request timeout."
                )

        return response


    @app.post(
        "/analyze/prompt",
        tags=["Analyze"],
        response_model=AnalyzePromptResponse,
        status_code=status.HTTP_200_OK,
        description="Analyze a prompt and return the sanitized prompt and the results of the scanners",
    )
    async def submit_analyze_prompt(
        request: AnalyzePromptRequest,
        # _: Annotated[bool, Depends(check_auth)],
        response: Response,
        input_scanners: List[InputScanner] = Depends(input_scanners_func),
    ) -> AnalyzePromptResponse:
        LOGGER.debug("Received analyze prompt request", request_prompt=request.prompt)

        if request.scanners_suppress is not None and len(request.scanners_suppress) > 0:
            LOGGER.debug("Suppressing scanners", scanners=request.scanners_suppress)
            input_scanners = [
                scanner
                for scanner in input_scanners
                if type(scanner).__name__ not in request.scanners_suppress
            ]

        with concurrent.futures.ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            try:
                start_time = time.time()
                sanitized_prompt, results_valid, results_score = await asyncio.wait_for(
                    loop.run_in_executor(
                        executor,
                        scan_prompt,
                        input_scanners,
                        request.prompt,
                        config.app.scan_fail_fast,
                    ),
                    timeout=config.app.scan_prompt_timeout,
                )
                pipe = pipeline("text-classification", model="jackhhao/jailbreak-classifier")
                jailbreak_results = pipe(request.prompt)
                for jailbreak_result in jailbreak_results:
                    if jailbreak_result["label"] == "jailbreak":
                        results_score["JailBreak"] = round(jailbreak_result["score"], 2)
                        results_valid["JailBreak"] = False
                        break
                    else:
                        results_score["JailBreak"] = -1.0
                        results_valid["JailBreak"] = False
                # for scanner, valid in results_valid.items():
                #     scanners_valid_counter.add(
                #         1, {"source": "input", "valid": valid, "scanner": scanner}
                #     )
                state = load_state()
                job_id = generate_unique_job_id(state.keys())
                state[job_id] = {"original_prompt": request.prompt,
                                 "sanitized_prompt": sanitized_prompt,
                                 "timestamp": str(datetime.now())}
                save_state(state)
                response = AnalyzePromptResponse(
                    sanitized_prompt=sanitized_prompt,
                    is_valid=all(results_valid.values()),
                    scanners=results_score,
                    job_id = job_id
                )

                elapsed_time = time.time() - start_time
                LOGGER.debug(
                    "Sanitized prompt response returned",
                    scores=results_score,
                    elapsed_time_seconds=round(elapsed_time, 6),
                )
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Request timeout."
                )

        return response
    

    @app.get(
        "/getScannerList",
        tags=["Scanner"],
        status_code=status.HTTP_200_OK,
        description="Provide the Scanner List based on scanner type",
    )
    async def get_scanner_list(scanner_type: str="Input", 
                               output_scanners: List[OutputScanner] = Depends(output_scanners_func),
                               input_scanners: List[InputScanner] = Depends(input_scanners_func)):
        try:
            if scanner_type == "Input":
                return {"scanners": [type(x).__name__ for x in input_scanners]}
            else:
                return {"scanners":[type(x).__name__ for x in output_scanners]}
        except Exception as e:
            print(e)
            raise HTTPException(
                status_code=500, detail="Issue While fetching scanner list"
            )

    @app.on_event("shutdown")
    async def shutdown_event():
        LOGGER.info("Shutting down app...")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request, exc):
        LOGGER.warning(
            "HTTP exception", exception_status_code=exc.status_code, exception_detail=exc.detail
        )

        return JSONResponse(
            {"message": str(exc.detail), "details": None}, status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        LOGGER.warning("Invalid request", exception=str(exc))

        response = {"message": "Validation failed", "details": exc.errors()}
        return JSONResponse(
            jsonable_encoder(response), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
