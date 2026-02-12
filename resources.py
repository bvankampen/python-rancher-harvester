#!/usr/bin/env python3

from modules.utils import load_blueprint, load_config, print_resources
from modules.harvester import Harvester

import argparse
import logging

logger = logging.getLogger(__name__)


def resources(config, blueprint):
    harvester = Harvester(config, blueprint)
    data = harvester.get_resources()
    print_resources(data)


def set_logging(config, log_level, log_filename):
    if log_level == "":
        if "logging" in config:
            if "level" in config["logging"]:
                log_level = config["logging"]["level"]
            else:
                log_level = "error"
        else:
            log_level = "error"
    if log_filename == "":
        if "logging" in config:
            if "filename" in config["logging"]:
                log_filename = config["logging"]["filename"]
            else:
                log_filename = ""
        else:
            log_filename = ""

    logging.basicConfig(
        filename=log_filename,
        level=int(getattr(logging, log_level.upper())),
        format="%(levelname)s - %(message)s",
    )

    logger.info(f"Loglevel set to {log_level.upper()}")


def main():
    parser = argparse.ArgumentParser(
        description="Provisioning Virtual Machines and Clusters on Harvester",
        add_help=True,
    )

    parser.add_argument("clustername", help="name of the cluster")
    parser.add_argument("--loglevel", help="loglevel", default="")
    parser.add_argument("--logfile", help="logfile name", default="")

    args = parser.parse_args()

    config = load_config("./config")
    blueprint = {"harvester": {"cluster_name": args.clustername }}

    set_logging(config, args.loglevel, args.logfile)

    if blueprint is not None:
        resources(config, blueprint)


if __name__ == "__main__":
    main()
