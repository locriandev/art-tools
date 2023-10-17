import sys
import traceback
from typing import Optional

import click

from elliottlib import Runtime
from elliottlib.bzutil import BugTracker
from elliottlib.cli.common import cli
from elliottlib.cli.find_bugs_sweep_cli import FindBugsMode
from elliottlib.metadata import Metadata


class FindBugsCVEs(FindBugsMode):
    def __init__(self, runtime: Runtime):
        super().__init__(
            status={'ON_QA', 'VERIFIED', 'RELEASE_PENDING'},
            cve_only=True,
        )

        self.runtime = runtime
        self.logger = self.runtime.logger

    def run(self):
        exit_code = 0

        for b in [self.runtime.get_bug_tracker('jira'), self.runtime.get_bug_tracker('bugzilla')]:
            try:
                self._find_bugs_cve(b)
            except Exception as e:
                self.logger.error(traceback.format_exc())
                self.logger.error(f'exception with {b.type} bug tracker: {e}')
                exit_code = 1
        sys.exit(exit_code)

    def _find_bugs_cve(self, bug_tracker: BugTracker):
        statuses = sorted(self.status)
        tr = bug_tracker.target_release()
        self.logger.info(f"Searching {bug_tracker.type} for bugs with status {statuses} and target releases: {tr}")

        bugs = self.search(bug_tracker_obj=bug_tracker, verbose=self.runtime.debug)
        # TODO remove
        bugs = [bug for bug in bugs if bug.id == 'OCPBUGS-31140']
        self.logger.info(f"Found {len(bugs)} bugs: {', '.join(sorted(str(b.id) for b in bugs)) or []}")

        for bug in bugs:
            try:
                pscomponent = [keyword.split(':')[-1] for keyword in bug.keywords if 'pscomponent' in keyword][0]
                self.logger.info(f'{bug.id} - {pscomponent}')
                latest_build = self._find_latest_build(pscomponent)

                if latest_build:
                    self.logger.info(f'Found build for {pscomponent}: {latest_build["nvr"]}')
                else:
                    self.logger.warning(f'No build found build for {pscomponent}')

            except IndexError:
                self.logger.warning('bug %s does not have a pscomponent set', bug.id)

    def _find_meta_from_pscomponent(self, pscomponent: str) -> Optional[Metadata]:
        """
        Give a pscomponent label, return the Metadata object associated with that Brew component
        """

        if 'container' in pscomponent:
            metas = self.runtime.image_metas()
        else:
            metas = self.runtime.rpm_metas()

        for meta in metas:
            if meta.get_component_name() == pscomponent:
                self.logger.info('Found %s associated with pscomponent %s', meta.name, pscomponent)
                return meta

        self.logger.warning('Could not associate %s with any image/rpm', pscomponent)
        return None

    def _find_latest_build(self, pscomponent: str):
        meta = self._find_meta_from_pscomponent(pscomponent)
        if not meta:
            return  # TODO

        return meta.get_latest_build(
            component_name=pscomponent,
            el_target=meta.branch_el_target()
        )


@cli.command("find-bugs:cve", short_help="Find CVEs with missing information")
@click.pass_obj
def find_bugs_cve_cli(runtime: Runtime):
    """Find tracker bugs for the target-releases, that:\n
- are ON_QA or higher\n
- are not attached to an advisory\n
- do not have an unshipped build for their pscomponent\n

\b
    $ elliott -g openshift-4.15 find-bugs:cve

"""

    runtime.initialize(mode='both', disabled=True)
    find_bugs_obj = FindBugsCVEs(runtime)
    find_bugs_obj.run()



