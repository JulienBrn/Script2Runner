from __future__ import annotations
from typing_extensions import Self
from pathlib import Path
import numpy as np, pandas as pd
import sys
from typing import List, Dict, Literal, Optional, Tuple, Type, Any, Union, ClassVar, TypeVar, Callable, Generic, Mapping, final, Set
from dataclasses import dataclass, field
from pydantic import BaseModel, TypeAdapter, Field, ValidationError, model_validator, ModelWrapValidatorHandler, ConfigDict, with_config, computed_field
from pydantic.dataclasses import dataclass as pydantic_dataclass
from datetime import datetime, date
import json, yaml
from pydantic_settings import BaseSettings, SettingsConfigDict, CliSubCommand, SettingsError
import argparse
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic.fields import FieldInfo
import datetime as dt
import logging
logger = logging.getLogger(__name__)

try:
    display("script2runner is testing if running in jupyter. conclusion: True")
    is_jupyter=True
    display = display
except:
    is_jupyter=False
    display=print


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



class Version(BaseModel):
    major_version: int
    minor_version: int
    patch_number: int

T = TypeVar("T", bound=BaseModel)
class RunInfo(BaseModel, Generic[T]):
    conda_env: Union[str]
    nprocs: Union[int, Literal["dynamic", "all", "unknown"]] = "unknown"
    gpu: Union[bool, Literal["dynamic", "unknown"]] = "unknown"
    expected_duration: Union[float, Literal["dynamic", "unknown"]] = "unknown"

    @final
    def get_dynamic_run_info(self, args: T) -> Self: 
        from dataclasses import asdict
        ret = self._dynamic_run_info(args)
        print(ret, type(ret))
        for k,v in ret.model_dump().items():
            if v == "dynamic":
                Exception(f"dynamic values should not be returned by dynamic_run_info, got dynamic for {k}")
        return ret
    
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

    def handle_args(self, source=sys.argv) -> T:
        if isinstance(source, Mapping):
            return self.args_type(**source) 
        if is_jupyter:
            return self.args_type(**self.jupyter_args)
        if source!=sys.argv:
            raise Exception("Parsing from other sources than sys.argv or a mapping is not yet supported")
        
        class GetDynamicRunInfo(BaseModel):
            export: bool = False
            output: Union[Path, Literal["stdout"]]= Field(default="stdout", description="File in which to export the run_info")
            format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the run_info")
            contents: Set[Literal["runinfo", "argsmodel"]] = {"runinfo", "argsmodel"}

            def handle(mself, argsm):
                if mself.export:
                    runinfo = self.run_info.get_dynamic_run_info(argsm).model_dump(mode="json")
                    argsmodel={k:v for k,v in argsm.model_dump(mode="json").items() if not k in ["config_file", "extra_runinfo"]}
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

        if a.run:
            a.run.extra_runinfo.handle(a.run)
            delattr(a.run, "config_file")
            delattr(a.run, "extra_runinfo")
            return a.run
        elif a.dryrun:
            a.dryrun.extra_runinfo.handle(a.dryrun)
            exit(0)
        else:
            raise Exception("No subcommands provided...")
        
        
        
        
        
        
        # class GetDynamicRunInfo(ArgsWithConfigFile):
        #     file: Union[Path, Literal["stdout"]]= Field(default="stdout", description="File in which to export the info")
        #     format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the run_info")
        #     def handle(self, mclass):
        #         data = self.dynamic_run_info
        #         export(data, self.file, self.format)

        













def read_arguments(Args: Type[T], jupyter_args=None) -> T:
    if is_jupyter:
      if jupyter_args is None:
          raise Exception("Unknown way of getting arguments...")
      return Args(**jupyter_args)
    else:
        class ArgsWithConfigFile(Args):
            config_file: List[Path] = []
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
        class GetDynamicRunInfo(ArgsWithConfigFile):
            file: Union[Path, Literal["stdout"]]= Field(default="stdout", description="File in which to export the info")
            format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the run_info")
            def handle(self, mclass):
                data = self.dynamic_run_info
                export(data, self.file, self.format)

        class CLI(BaseSettings, cli_parse_args=True, cli_implicit_flags=True,):
            run: CliSubCommand[ArgsWithConfigFile]
            get_schema: CliSubCommand[GetExportSchema] #Allows retrieval of arguments
            metadata: CliSubCommand[GetMetadata] #Allows retrieval of other information such as author, ...
            static_run_info: CliSubCommand[GetStaticRunInfo] #Allows retrieval of information on run environment requirements/impact
            dynamic_run_info: CliSubCommand[GetDynamicRunInfo]
            check: CliSubCommand[Args]
        
        try:
            a = CLI()
        except SettingsError as e:
            print(e)
            exit(2)
        except ValidationError as e:
            err_str = '\n   '.join([l for l in str(e).split('\n')[1:] if not "For further information visit" in l])
            print(f"Please check your input arguments as the following errors were found.\n   {err_str}")
            exit(2)
        for key in ["get_schema", "static_run_info", "metadata", "dynamic_run_info"]:
            if getattr(a, key):
                getattr(a, key).handle(Args)
                exit(0)
        if a.check:
            exit(0)
        
        if a.run:
            delattr(a.run, "config_file")
            return a.run
        else:
            raise Exception("No subcommands provided...")