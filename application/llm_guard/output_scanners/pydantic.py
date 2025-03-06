import json
import re

import regex

from llm_guard.util import get_logger, lazy_load_dep

from .base import Scanner
from typing import Union, List


class PydanticOutputParser(Scanner):
    

    def scan(self, prompt: str, output: str, only_json: bool = False) -> tuple[Union[str, List[str]], bool, float]:
        return "", True, 0.0

