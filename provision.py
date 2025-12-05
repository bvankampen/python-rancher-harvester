#!/usr/bin/env python3

from modules.utils import load_blueprint, load_config
from modules.rancher import Rancher
from modules.harvester import Harvester

DRY_RUN = False


def main():
    config = load_config("./config")
    blueprint = load_blueprint("cluster-test")

    rancher = Rancher(config)
    harvester = Harvester(config, blueprint)

    rancher.create_cluster(blueprint, DRY_RUN)
    rancher.wait_for_cluster(blueprint)
    harvester.create_vms(blueprint, DRY_RUN)


if __name__ == "__main__":
    main()
