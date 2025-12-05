import glob
import json
import yaml
import os
import base64

import logging

logger = logging.getLogger(__name__)


ENVIRONMENTAL_VARIABLE_PREFIX = "PRH_"


def load_file(file_name):
    data = {}
    with open(file_name, "r") as f:
        if file_name.endswith(".json"):
            data = json.load(f)
        if file_name.endswith(".yaml") or file_name.endswith(".yml"):
            data = yaml.safe_load(f)
    return data


def load_config_files(config_directory):
    config = {}
    config_files = glob.glob(f"{config_directory}/*")
    for config_file in config_files:
        if "example" not in config_file:
            config = config | load_file(config_file)
    return config


def load_environment_variables():
    vars = {}
    env_vars = os.environ
    for key in env_vars:
        if key.startswith(ENVIRONMENTAL_VARIABLE_PREFIX):
            value = env_vars[key]
            key = key.replace(ENVIRONMENTAL_VARIABLE_PREFIX, "").lower()
            vars[key] = value
    return vars


def load_config(config_directory):
    config = load_config_files(config_directory)
    config = config | load_environment_variables()
    return config


def load_blueprint(name):
    if name.endswith(".yaml"):
        blueprint_file = f"./blueprints/{name}"
    else:
        blueprint_file = f"./blueprints/{name}.yaml"

    if not os.path.exists(blueprint_file):
        logger.error(f"{blueprint_file} not found")
        return None
    return load_file(blueprint_file)


def merge_dict(dict_1, dict_2):
    dict_3 = {**dict_1, **dict_2}
    for key, value in dict_3.items():
        if key in dict_1 and key in dict_2:
            dict_3[key] = dict_1[key] | value
    return dict_3


def print_api_error(e):
    response = json.loads(e.body)
    if response["reason"] != "AlreadyExists":
        print(str(e))
    else:
        logging.warning(response["message"])


def b64encode(data):
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")


def b64decode(data):
    return base64.b64decode(data.encode("utf-8")).decode("utf-8")
