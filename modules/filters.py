import yaml
import json
import base64


def to_yaml(data):
    return yaml.dump(data)


def to_json(data):
    return json.dumps(data)


def b64encode(data):
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")
