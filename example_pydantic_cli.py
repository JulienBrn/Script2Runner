from pathlib import Path
import numpy as np, pandas as pd
from typing import List, Dict, Literal, Optional, Tuple, Type, Any
from pydantic import Field
from script2runner import CLI
from datetime import datetime, date, timezone
import beautifullogger, logging

logger = logging.getLogger(__name__)
beautifullogger.setup()

class Args(CLI):
    step: datetime = Field(default=datetime.now(tz=timezone.utc).astimezone())
    required_arg_for_test: int = Field(examples=[3])
    folder: Path = Field(default=".", description="Folder on which the program searches for the txt files")
    bin_size: int | Literal["auto"] = Field(default="auto", description="Size of the bins")
    bin_agg: Literal["max", "mean", "median", "min"] = "max"
    glob_pattern: str = "**/*.txt"
    out_folder: Path | Literal["__input_folder_path__"] = Field(default = "__input_folder_path__")
    show: bool = False
    overwrite: Literal["ask_user", "yes", "no"] = "ask_user"
    files: List[Tuple[Path, Path]] = Field(default=[("def_1", "def_2")])
    get_args_schema_as_dataclass_pickle: bool = False
    m_date: date = Field(default=date(year=2025, month=2, day=3))

a: Args = Args()


logger.info("Starting")
from time import sleep
for i in range(10):
    print(i)
    sleep(0.1)

print(a)
logger.info("Done")
