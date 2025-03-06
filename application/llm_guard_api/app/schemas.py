from typing import Dict, List, Callable, Union
import os
from pydantic import BaseModel, Field
from typing_extensions import Literal
from .config import AuthConfig, Config, get_config
from llm_guard.vault import Vault
from llm_guard.output_scanners.base import Scanner as OutputScanner
from .scanner import get_output_scanners
import structlog
LOGGER = structlog.getLogger(__name__)


class ScanPromptRequest(BaseModel):
    prompt: str = Field(title="Prompt")
    scanners_suppress: List[str] = Field(title="Scanners to suppress", default=[])


class ScanPromptResponse(BaseModel):
    is_valid: bool = Field(title="Whether the prompt is safe")
    scanners: Dict[str, float] = Field(title="Risk scores of individual scanners")


class AnalyzePromptRequest(ScanPromptRequest):
    pass


class AnalyzePromptResponse(ScanPromptResponse):
    sanitized_prompt: str = Field(title="Sanitized prompt")
    job_id: str = Field(title="job_id for each prompt")


class ScanOutputRequest(BaseModel):
    job_id: str = Field(title="Prompt")
    output: str = Field(title="Model output")
    scanners_suppress: List[str] = Field(title="Scanners to suppress", default=[])
    only_json: bool = Field(title="If only list of json is required", default=False)


class ScanOutputResponse(BaseModel):
    is_valid: bool = Field(title="Whether the output is safe")
    scanners: Dict[str, float] = Field(title="Risk scores of individual scanners")


class AnalyzeOutputRequest(ScanOutputRequest):
    pass


class AnalyzeOutputResponse(ScanOutputResponse):
    sanitized_output: Union[str, List[str]] = Field(title="Sanitized output")
