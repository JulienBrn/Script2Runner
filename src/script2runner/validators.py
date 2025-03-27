import sys, datetime as dt, logging, json, yaml, subprocess, re
from pathlib import Path
from typing import List, Dict, Literal, Optional, Tuple, Type, Any, Union, ClassVar, TypeVar, Callable, Generic, Mapping, final, Set, Annotated
from pydantic import BaseModel, Field, ValidationError, model_validator, ConfigDict, computed_field, AfterValidator, WithJsonSchema, GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue
import dataclasses

def conda_env_exists(s):
    p  = subprocess.run(f"conda rename -n '{s}' '{s}'", shell=True, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    if "already exists" in p.stdout.decode():
        return s
    else:
        raise ValueError(f"Conda environment {s} does not seem to exist")

class CondaEnv(BaseModel):
    env_name: Annotated[str, AfterValidator(conda_env_exists)]
    env_type: Literal["conda"] = "conda"
                        
    @computed_field
    @property
    def python_path(self) -> Path:
        return Path(sys.executable)

class Version(BaseModel):
    major_version: int
    minor_version: int
    patch_number: int

    @model_validator(mode='before')
    @classmethod
    def versionfromstr(cls, data: Any) -> Any:  
        if isinstance(data, str):  
            parts = data.split('.')
            try:
                parts = [int(p) for p in parts]
            except Exception:
                raise ValueError("Version numbers should be constituted of three integers separated by .")
            if len(parts) == 3:
                return dict(major_version=parts[0], minor_version=parts[1], patch_number=parts[2])
            else:
                raise ValueError("Version numbers should be constituted of three integers separated by .")
        return data

@dataclasses.dataclass
class PathConstraints:
    exists: Union[bool, None] = None
    pathtype: Literal["file", "folder", "any"] = "any" 
    suffix: Union[str, List[str]] = dataclasses.field(default_factory=lambda: [])
    patterns: Union[str, List[str]] = dataclasses.field(default_factory=lambda: [])
    enforce_pattern: bool=True

    all_patterns: List[str] = dataclasses.field(init=False)
    repattern: Union[str, None] = dataclasses.field(init=False)

    def __post_init__(self):
        if isinstance(self.patterns, str):
            self.patterns = [self.patterns]
        if isinstance(self.suffix, str):
            self.suffix = [self.suffix]
        self.all_patterns = [f"{re.escape(s)}$" for s in self.suffix] + self.patterns
        if len(self.all_patterns) >1:
            self.repattern = "("+ ")|(".join(self.all_patterns) + ")"
        elif len(self.all_patterns) == 1:
            self.repattern = self.all_patterns[0]
        else:
            self.repattern = None


    def __get_pydantic_core_schema__(
        self, source: Type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:

        schema = handler(source)
        return core_schema.no_info_after_validator_function(self.validate, schema)
    
    def __get_pydantic_json_schema__(
        self, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        if "pattern" in json_schema and self.repattern:
            raise Exception(f"Combining patterns with an and is not yet supported.\nTrying to combine {json_schema['pattern']} and {self.repattern}")
        elif self.repattern:
            json_schema["pattern"] = self.repattern

        return json_schema

    def validate(self, p):
        if not isinstance(p, Path):
            raise TypeError(f"PathConstraints can only be applied to Path, got {type(p)}")
        if self.exists is None: pass
        elif self.exists:
            if not p.exists():
                raise ValueError(f'Path {p} does not exist')
        elif not self.exists and p.exists():
            raise ValueError(f'Path {p} exists and should not')

        if self.pathtype!="any":
            if p.exists():
                if type=="folder" and not p.is_dir():
                    raise ValueError(f'Path {p} should be a folder')
                elif type=="file" and p.is_dir():
                    raise ValueError(f'Path {p} should be a file. Got a folder')
            if re.match(self.repattern, str(p)):
                return p
            else:
                raise ValueError(f'Path {p} should match one of the following patterns {self.patterns}')
        return p
    

# @dataclasses.dataclass
# class OptionConstraints:
#     f: Callable[[], ]

#     all_patterns: List[str] = dataclasses.field(init=False)
#     repattern: Union[str, None] = dataclasses.field(init=False)

#     def __post_init__(self):
#         if isinstance(self.patterns, str):
#             self.patterns = [self.patterns]
#         if isinstance(self.suffix, str):
#             self.suffix = [self.suffix]
#         self.all_patterns = [f"{re.escape(s)}$" for s in self.suffix] + self.patterns
#         if len(self.all_patterns) >1:
#             self.repattern = "("+ ")|(".join(self.all_patterns) + ")"
#         elif len(self.all_patterns) == 1:
#             self.repattern = self.all_patterns[0]
#         else:
#             self.repattern = None


#     def __get_pydantic_core_schema__(
#         self, source: Type[Any], handler: GetCoreSchemaHandler
#     ) -> core_schema.CoreSchema:

#         schema = handler(source)
#         return core_schema.no_info_after_validator_function(self.validate, schema)
    
#     def __get_pydantic_json_schema__(
#         self, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
#     ) -> JsonSchemaValue:
#         json_schema = handler(core_schema)
#         json_schema = handler.resolve_ref_schema(json_schema)
#         if "pattern" in json_schema and self.repattern:
#             raise Exception(f"Combining patterns with an and is not yet supported.\nTrying to combine {json_schema['pattern']} and {self.repattern}")
#         elif self.repattern:
#             json_schema["pattern"] = self.repattern

#         return json_schema

#     def validate(self, p):
#         if not isinstance(p, Path):
#             raise TypeError(f"PathConstraints can only be applied to Path, got {type(p)}")
#         if self.exists is None: pass
#         elif self.exists:
#             if not p.exists():
#                 raise ValueError(f'Path {p} does not exist')
#         elif not self.exists and p.exists():
#             raise ValueError(f'Path {p} exists and should not')

#         if self.pathtype!="any":
#             if p.exists():
#                 if type=="folder" and not p.is_dir():
#                     raise ValueError(f'Path {p} should be a folder')
#                 elif type=="file" and p.is_dir():
#                     raise ValueError(f'Path {p} should be a file. Got a folder')
#             if re.match(self.repattern, str(p)):
#                 return p
#             else:
#                 raise ValueError(f'Path {p} should match one of the following patterns {self.patterns}')
#         return p