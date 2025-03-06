import logging
from typing import Dict, List

from artcommonlib.konflux.konflux_build_record import KonfluxBuildRecord
from doozerlib import brew


class PackageRpmFinder:
    """
    This class serves a cache, mapping package names as they are listed in a Konflux build record to a list of Brew RPMs
    to limit redundant calls to Brew API
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._package_to_rpms: Dict[str, List[Dict]] = {}

    def get_brew_rpms_from_build_record(self, build_record: KonfluxBuildRecord, runtime: "doozerlib.Runtime") -> List[Dict]:
        installed_packages = build_record.installed_packages

        # Query Brew to fetch RPMs included in packages not yet cached
        caching_packages = [p for p in installed_packages if not self._package_to_rpms.get(p, None)]
        with runtime.shared_koji_client_session() as session:
            self._logger.info('Caching RPM build info for package NVRs %s', ', '.join(caching_packages))

            # Get package build IDS from package names
            with session.multicall(strict=True) as multicall:
                tasks = [multicall.getBuild(package) for package in caching_packages]
            builds = [task.result for task in tasks]

            # For some reason, some builds cannot be found in Brew.
            # Remove them from the caching packages to avoid useless API calls
            for i, build in enumerate(builds):
                if not build:
                    build_not_found = caching_packages.pop(i)
                    self._logger.warning('Package build %s could not be found in Brew '
                                         'and will be excluded from the check', build_not_found)
                    builds.pop(i)
                    installed_packages.pop(installed_packages.index(build_not_found))

            # Get RPM list from package build IDs using koji_api.listBuildRPMs
            installed_rpms: List[List[Dict]] = brew.list_build_rpms(caching_packages, session)
            for package_build, rpm_builds in zip(caching_packages, installed_rpms):
                self._package_to_rpms[package_build] = rpm_builds

        # Gather RPMs associated to given KonfluxBuildRecord
        results = []
        for package in installed_packages:
            results.extend(self._package_to_rpms[package])
        return results
