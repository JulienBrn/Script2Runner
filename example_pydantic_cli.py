#Run using 'python example_pydantic_cli.py run --req 5' for example

from pathlib import Path
from pydantic._internal._generics import PydanticGenericMetadata
from typing_extensions import Unpack
import numpy as np, pandas as pd
from typing import List, Dict, Literal, Optional, Tuple, Type, Any, Annotated, Sequence
from script2runner import Runner, RunInfo, MetadataInfo, PathConstraints, CondaEnv, nice_print_pydantic_error
from pydantic import BaseModel, ConfigDict, ValidationError, Field
from datetime import datetime, date, timezone


class Args(BaseModel):
    i: int =3
    path: Annotated[Path, PathConstraints(exists=True, suffix=".csv"), PathConstraints(exists=True)]
    req: int



runner = Runner(Args, RunInfo(python_env=CondaEnv(env_name="si2")), MetadataInfo(version="0.0.1"))
try:
    a = runner.handle_args()
except ValidationError as e:
    print(nice_print_pydantic_error(e))
    exit(2)
print(a)
