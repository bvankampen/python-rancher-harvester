import jinja2
import yaml
from .filters import to_yaml, to_json, b64encode


class Template:
    def __init__(self, name):
        self.name = name

    def parse(self, **data):
        env = jinja2.Environment()
        env.filters["to_yaml"] = to_yaml
        env.filters["to_json"] = to_json
        env.filters["b64encode"] = b64encode
        with open(f"./templates/{self.name}.yaml.j2") as f:
            template = env.from_string(f.read())
        parsed_template = template.render(data)
        return parsed_template
