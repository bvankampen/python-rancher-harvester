#!/usr/bin/env python3

from modules.utils import load_blueprint, load_config
from modules.rancher import Rancher
from modules.harvester import Harvester

import argparse
import logging

logger = logging.getLogger(__name__)


def provision(config, blueprint, args):
    if "cluster" in blueprint:
        rancher = Rancher(config)
        rancher.create_cluster(blueprint)

    harvester = Harvester(config, blueprint)
    harvester.create_vms(blueprint, args.updatevm, args.vms)


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
        level=logging.getLevelName(log_level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    logger.info(f"Loglevel set to {log_level.upper()}")


def main():
    parser = argparse.ArgumentParser(
        description="Provisioning Virtual Machines and Clusters on Harvester",
        add_help=True,
    )

    parser.add_argument("blueprint", help="name of the blueprint")
    parser.add_argument(
        "--updatevm", help="update vm even if they exists", action="store_true"
    )
    parser.add_argument(
        "--vms",
        help="VM names (comma seperated) in case updatevm is used, if empty all vms are updated",
        default="",
    )
    parser.add_argument("--loglevel", help="loglevel", default="")
    parser.add_argument("--logfile", help="logfile name", default="")

    args = parser.parse_args()

    config = load_config("./config")
    blueprint = load_blueprint(args.blueprint)

    set_logging(config, args.loglevel, args.logfile)

    if blueprint is not None:
        provision(config, blueprint, args)


if __name__ == "__main__":
    main()
