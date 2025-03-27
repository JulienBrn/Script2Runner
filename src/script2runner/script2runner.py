from __future__ import annotations
from typing_extensions import Self
from pathlib import Path
import sys, datetime as dt, logging, json, yaml, subprocess, re
from typing import List, Dict, Literal, Optional, Tuple, Type, Any, Union, ClassVar, TypeVar, Callable, Generic, Mapping, final, Set, Annotated
from dataclasses import dataclass
from pydantic import BaseModel, Field, ValidationError, model_validator, ConfigDict, computed_field, AfterValidator, WithJsonSchema
from pydantic_settings import BaseSettings, CliSubCommand, SettingsError
from script2runner.validators import PathConstraints, CondaEnv, Version
logger = logging.getLogger(__name__)

def nice_print_pydantic_error(e):
    return '\n   '.join([l for l in str(e).split('\n')[1:] if not "For further information visit" in l])

def export(data, file, format):
    if format=="auto":
        if file=="stdout" or file.suffix.lower()  in [".yaml", ".yml"]:
            format = "yaml"
        else:
            format = "json"
    if format == "yaml":
        s = yaml.dump(data)
    elif format =="json":
        s = json.dumps(data, indent=4)
    else:
        raise Exception("Unknown format")
    if file == "stdout":
        print(s)
    else:
        with file.open("w") as f:
            f.write(s)


T = TypeVar("T", bound=BaseModel)
    

class PythonPath(BaseModel):
    env_type: Literal["from_interpreter_path"] = "from_interpreter_path"
    python_path: Annotated[Path, PathConstraints(exists=True, suffix="python", pathtype="file")]

class DynamicRunInfo(BaseModel, Generic[T]):
    nprocs: Union[int, Literal["all", "unknown"]] = "unknown"
    gpu: Union[bool, Literal["unknown"]] = "unknown"
    expected_duration: Union[float, Literal["unknown"]] = "unknown"
    
    @computed_field
    @property
    def python_path(self) -> Path:
        return Path(sys.executable)
    
    model_config = ConfigDict(extra='allow')


class RunInfo(BaseModel, Generic[T]):
    python_env: Annotated[Union[CondaEnv, PythonPath], Field(discriminator="env_type")]
    nprocs: Union[int, Literal["dynamic", "all", "unknown"]] = "unknown"
    gpu: Union[bool, Literal["dynamic", "unknown"]] = "unknown"
    expected_duration: Union[float, Literal["dynamic", "unknown"]] = "unknown"

    def get_dynamic_run_info(self, args: T) -> DynamicRunInfo[T]: 
        return DynamicRunInfo()
    
    def _dynamic_run_info(self, args: T) -> Self:
        return self

    model_config = ConfigDict(extra='allow')



class MetadataInfo(BaseModel):
    maintainer: Union[str, None] = None
    version: Union[Version, None] = None

    @computed_field
    @property
    def git_version(self) -> Union[str, None] : return None

    @computed_field
    @property
    def last_modified(self) -> Union[dt.datetime, None] : return None

    model_config = ConfigDict(extra='allow')

@dataclass
class Runner(Generic[T]):
    args_type: Type[T]
    run_info: RunInfo
    metadata: MetadataInfo = MetadataInfo()
    jupyter_args: Union[Dict[str, Any], None] = None

    def handle_args(self, source=sys.argv, is_running_in_jupyter: Union[bool, Literal["auto"]]="auto") -> T:
        if isinstance(source, Mapping):
            return self.args_type(**source) 
        if is_running_in_jupyter =="auto":
            from script2runner.utils import is_using_jupyter
            is_running_in_jupyter = is_using_jupyter()
        if is_running_in_jupyter:
            return self.args_type(**self.jupyter_args)
        if source!=sys.argv:
            raise Exception("Parsing from other sources than sys.argv or a mapping is not yet supported")
        
        class GetDynamicRunInfo(BaseModel):
            export: bool = False
            output: Union[Path, Literal["stdout"]]= Field(default="stdout", description="File in which to export the run_info")
            format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the run_info")
            contents: Set[Literal["runinfo", "argsmodel", "validation_errors"]] = {"runinfo", "argsmodel", "validation_errors"}

            def handle(mself, argsmodel):
                if mself.export:
                    runinfo = self.run_info.get_dynamic_run_info(argsmodel).model_dump(mode="json")
                    data = dict(runinfo=runinfo, argsmodel=argsmodel)
                    data = {k:v for k, v in data.items() if k in mself.contents}
                    if len(data) == 1:
                        data = data[list(data.keys())[0]]
                    export(data, mself.output, mself.format)

        class ArgsWithConfigFile(self.args_type):
            config_file: List[Path] = []
            extra_runinfo: GetDynamicRunInfo = GetDynamicRunInfo()
    
            @model_validator(mode='wrap')
            @classmethod
            def handle_config(cls, data: Any, handler):
                if "config_file" in data:
                    c = {}
                    for p in data["config_file"]:
                        p= Path(p)
                        if not p.exists():
                            raise Exception(f"File {p} does not exist")
                        with p.open("r") as f:
                            if p.suffix==".json":
                                d = json.load(f) 
                            elif p.suffix in [".yml", ".yaml"]:
                                d = yaml.safe_load(f)
                            else:
                                raise Exception(f"Unknown suffix {p.suffix} for file {p}")
                        c.update(d)
                    return handler(c | {k:v for k,v in data.items()})
                else:
                    return handler(data)
                
        class GetExportSchema(BaseModel):
            output: Union[Path, Literal["stdout"]]= Field(default="stdout", description="File in which to export the schema")
            format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the schema dictionary")
            def handle(mself):
                data = self.args_type.model_json_schema()
                export(data, mself.output, mself.format)

        class GetRunInfo(BaseModel):
            output: Union[Path, Literal["stdout"]]= Field(default="stdout", description="File in which to export the run_info")
            format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the run_info")
            def handle(mself):
                data = self.run_info.model_dump(mode="json")
                export(data, mself.output, mself.format)
        class GetMetadata(BaseModel):
            output: Union[Path, Literal["stdout"]]= Field(default="stdout", description="File in which to export the metadata")
            format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the run_info")
            def handle(mself):
                data = self.metadata.model_dump(mode="json")
                export(data, mself.output, mself.format)

        class CLI(BaseSettings, cli_parse_args=True, cli_implicit_flags=True,):
            run: CliSubCommand[ArgsWithConfigFile]
            argschema: CliSubCommand[GetExportSchema] #Allows retrieval of arguments
            metadata: CliSubCommand[GetMetadata] #Allows retrieval of other information such as author, ...
            runinfo: CliSubCommand[GetRunInfo] #Allows retrieval of information on run environment requirements/impact
            dryrun: CliSubCommand[ArgsWithConfigFile]
        
        try:
            a = CLI()
        except SettingsError as e:
            print(e)
            exit(2)
        except ValidationError as e:
            err_str = '\n   '.join([l for l in str(e).split('\n')[1:] if not "For further information visit" in l])
            print(f"Please check your input arguments as the following errors were found.\n   {err_str}")
            exit(2)
        for key in ["argschema", "metadata", "runinfo"]:
            if getattr(a, key):
                getattr(a, key).handle()
                exit(0)
        r = a.run if a.run else a.dryrun if a.dryrun else None
        if r:
            m = self.args_type.model_construct(**{k:v for k,v in r.model_dump().items() if not k in ["config_file", "extra_runinfo"]})
            r.extra_runinfo.handle(m)
            if a.dryrun:
                exit(0)
            return m
        else:
            raise Exception("No subcommands provided...")
        


