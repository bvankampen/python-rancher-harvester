#!/usr/bin/env python3

from modules.utils import load_blueprint, load_config
from modules.rancher import Rancher
from modules.harvester import Harvester

import argparse

DRY_RUN = False


def main():
    parser = argparse.ArgumentParser(
        description="Provisioning Virtual Machines and Clusters on Harvester",
        add_help=True,
    )

    parser.add_argument("blueprint", help="name of the blueprint")

    args = parser.parse_args()

    config = load_config("./config")
    blueprint = load_blueprint(args.blueprint)

    if blueprint is None:
        return

    if "cluster" in blueprint:
        rancher = Rancher(config)
        rancher.create_cluster(blueprint)

    harvester = Harvester(config, blueprint)
    harvester.create_vms(blueprint)


if __name__ == "__main__":
    main()
