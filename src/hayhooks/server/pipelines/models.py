from typing import Any, Dict

from pandas import DataFrame
from pydantic import BaseModel, ConfigDict, create_model

from hayhooks.server.utils.create_valid_type import handle_unsupported_types

UNSUPPORTED_TYPES_MAPPING: Dict[Any, Any] = {DataFrame: dict}

try:
    from qdrant_client.http import models

    UNSUPPORTED_TYPES_MAPPING[models.Filter] = dict

except ImportError:
    pass


class PipelineDefinition(BaseModel):
    name: str
    source_code: str


def get_request_model(pipeline_name: str, pipeline_inputs):
    """
    Inputs have this form:
    {
        'first_addition': { <-- Component Name
            'value': {'type': <class 'int'>, 'is_mandatory': True}, <-- Input
            'add': {'type': typing.Optional[int], 'is_mandatory': False, 'default_value': None}, <-- Input
        },
        'second_addition': {'add': {'type': typing.Optional[int], 'is_mandatory': False}},
    }
    """
    request_model = {}
    config = ConfigDict(arbitrary_types_allowed=True)

    for component_name, inputs in pipeline_inputs.items():
        component_model = {}
        for name, typedef in inputs.items():
            try:
                input_type = handle_unsupported_types(typedef["type"], UNSUPPORTED_TYPES_MAPPING)
            except TypeError as e:
                print(f"ERROR at {component_name!r}, {name}: {typedef}")
                raise e
            component_model[name] = (
                input_type,
                typedef.get("default_value", ...),
            )
        request_model[component_name] = (create_model("ComponentParams", **component_model, __config__=config), ...)

    return create_model(f"{pipeline_name.capitalize()}RunRequest", **request_model, __config__=config)


def get_response_model(pipeline_name: str, pipeline_outputs):
    """
    Outputs have this form:
    {
        'second_addition': { <-- Component Name
            'result': {'type': "<class 'int'>"}  <-- Output
        },
    }
    """
    response_model = {}
    config = ConfigDict(arbitrary_types_allowed=True)
    for component_name, outputs in pipeline_outputs.items():
        component_model = {}
        for name, typedef in outputs.items():
            output_type = typedef["type"]
            component_model[name] = (handle_unsupported_types(output_type, UNSUPPORTED_TYPES_MAPPING), ...)
        response_model[component_name] = (create_model("ComponentParams", **component_model, __config__=config), ...)

    return create_model(f"{pipeline_name.capitalize()}RunResponse", **response_model, __config__=config)


def convert_component_output(component_output):
    """
    Converts outputs from a component as a dict so that it can be validated against response model

    Component output has this form:

    "documents":[
        {"id":"818170...", "content":"RapidAPI for Mac is a full-featured HTTP client."}
    ]

    """
    result = {}
    for output_name, data in component_output.items():

        def get_value(data):
            if hasattr(data, "to_dict") and "init_parameters" in data.to_dict():
                return data.to_dict()["init_parameters"]
            elif hasattr(data, "to_dict"):
                return data.to_dict()
            else:
                return data

        if type(data) is list:
            result[output_name] = [get_value(d) for d in data]
        else:
            result[output_name] = get_value(data)
    return result
