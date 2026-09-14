# Hackweek 2025 Project

## Usage

- install python requirements in `requirements.txt`
- `export PRH_API_TOKEN=<rancher-api-token>` or define `api_token` in blueprint or config
- Run `python3 provision.py <blueprint>` to provision virtual machines and clusters.
- Run `python3 cleanup.py <blueprint>` to safely deprovision and clean up virtual machines, PVC disks, cloud-init configuration, CSI cloud credentials, networks, IP pools, and Rancher clusters created by the blueprint.

## Todo

- [x] Logging and error handling
- [x] Configuring of (pass through) NVME disks
- [ ] Automatic scheduling on VM based on free PCIE resources
- [x] Deleting and cleanup of VMs, clusters and resources
- [ ] Ansible Module

## Description

Create Python modules for provisioning VMs with options currently not supported by other provisioning tools (like PCIe Devices and CPU Type), these modules can also be used to create an Ansible module.

## Goals

- Create Python modules to provision VMs in Harvester with support for PCIe Devices and Cloudinit
- Create Python modules to provision RKE2 Cluster
- Look into the possibility to create Ansible Modules.

## Resources

- https://hackweek.opensuse.org/25/projects/python-modules-for-harvester-vm-provisioning-and-rancher-rke2-provisioning
