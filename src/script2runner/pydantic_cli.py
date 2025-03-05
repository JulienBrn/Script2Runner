from pathlib import Path
import numpy as np, pandas as pd
import sys
from typing import List, Dict, Literal, Optional, Tuple, Type, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, TypeAdapter, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass
from datetime import datetime, date
import json, yaml
from pydantic_settings import BaseSettings, SettingsConfigDict, CliSubCommand
import argparse
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic.fields import FieldInfo
import logging
logger = logging.getLogger(__name__)

class ExportSchema(BaseModel):
    export_schema : bool = Field(default=False, description="Export the current schema for arguments. Stops any other processing.")
    schema_file: Path | Literal["stdout"]= Field(default=Path("schema.json"), description="File in which to export the schema")
    export_format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the schema dictionary")

class RunInfo(BaseModel):
    export_runinfo : bool = Field(default=False, description="Export the current run_info. Stops any other processing.")
    runinfo_file: Path | Literal["stdout"]= Field(default=Path("run_info.json"), description="File in which to export the run_info")
    export_format : Literal["json", "yaml", "auto"] = Field(default="auto", description="Format in which to export the run_info")



class ConfigFile(BaseModel):
    config_file: List[Path] = Field(default=[], description="Config files from which to read arguments values. Config files  will be overwritten by other command line arguments")
    

class ExportSchemaCLI(ExportSchema, BaseSettings, cli_parse_args=True, cli_ignore_unknown_args=True, cli_implicit_flags=True): pass
class ConfigFileCLI(ConfigFile, BaseSettings, cli_parse_args=True, cli_ignore_unknown_args=True, cli_implicit_flags=True): pass
class RunInfoCLI(RunInfo, BaseSettings, cli_parse_args=True, cli_ignore_unknown_args=True, cli_implicit_flags=True): pass

config_file_dict = {}
class FileConfigSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        
        return config_file_dict[field_name], field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        return value
    
    def __call__(self) -> Dict[str, Any]:
        global config_file_dict
        return config_file_dict

class CLI(ExportSchema, RunInfo, ConfigFile, BaseSettings, cli_parse_args=True, cli_implicit_flags=True):

    def __init__(self, **kwargs):
        no_run = False
        if "--help" in sys.argv:
            super().__init__(**kwargs)
            exit()
        export = ExportSchemaCLI()
        if export.export_schema:
            schema = self.__class__.model_json_schema()
            schema["properties"] = {k:v for k,v in schema["properties"].items() if not k in ExportSchema.model_fields and not k in ConfigFile.model_fields and not k in RunInfo.model_fields}
            if export.schema_file == "stdout":
                if export.export_format=="yaml":
                    print(yaml.dump(schema))
                else:
                    print(json.dumps(schema))
            else:
                if export.export_format=="auto":
                    export.export_format = export.schema_file.suffix[1:]
                with export.schema_file.open("w") as f:
                    if export.export_format=="yaml":
                        yaml.safe_dump(schema, f)
                    else:
                        json.dump(schema, f, indent=4)
            no_run = True

        if not hasattr(self, "_run_info"):
            self._run_info = {}

        run_info_export = RunInfoCLI()
        if run_info_export.export_runinfo:
            if run_info_export.runinfo_file == "stdout":
                if run_info_export.export_format=="yaml":
                    print(yaml.dump(self._run_info))
                else:
                    print(json.dumps(self._run_info))
            else:
                if run_info_export.export_format=="auto":
                    run_info_export.export_format = run_info_export.schema_file.suffix[1:]
                with run_info_export.runinfo_file.open("w") as f:
                    if run_info_export.export_format=="yaml":
                        yaml.safe_dump(self._run_info, f)
                    else:
                        json.dump(self._run_info, f, indent=4)
            no_run = True

        if no_run:
            exit()
        config_files: ConfigFile = ConfigFileCLI()
        c = {}
        for p in config_files.config_file:
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
        global config_file_dict
        config_file_dict = c
        try:
            super().__init__(**kwargs)
        except Exception as e:
            error_info = "\n\t".join(str(e).split("\n")[1:-1])
            logger.error("Error while reading arguments\n\t" + error_info + "\n\tUse the --help option to display command line usage")
            exit() 

            
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            FileConfigSettingsSource(settings_cls),
            env_settings,
            file_secret_settings,
        )