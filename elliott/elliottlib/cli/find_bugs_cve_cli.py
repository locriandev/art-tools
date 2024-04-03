import json
import sys
import traceback
from typing import Optional

import click

from artcommonlib import exectools
from artcommonlib.constants import BREW_POOL_SIZE
from artcommonlib.util import isolate_major_minor_in_group
from elliottlib import Runtime
from elliottlib.brew import BuildStates
from elliottlib.cli.common import cli
from elliottlib.cli.find_bugs_sweep_cli import FindBugsMode
from elliottlib.metadata import Metadata


class FindBugsCVEs(FindBugsMode):
    def __init__(self, runtime: Runtime):
        super().__init__(
            status=['ON_QA', 'VERIFIED', 'RELEASE_PENDING'],
            cve_only=True,
        )

        self.runtime = runtime
        self.logger = self.runtime.logger
        self.issues = {}

    def run(self):
        exit_code = 0

        for tracker in [self.runtime.get_bug_tracker('jira'), self.runtime.get_bug_tracker('bugzilla')]:
            try:
                # Find bugs
                statuses = sorted(self.status)
                tr = tracker.target_release()
                self.logger.info(f"Searching {tracker.type} for bugs with status {statuses} and target releases: {tr}")
                bugs = self.search(bug_tracker_obj=tracker, verbose=self.runtime.debug)
                self.logger.info(f"Found {len(bugs)} bugs: {', '.join(sorted(str(b.id) for b in bugs)) or []}")

                # Find builds
                with self.runtime.pooled_koji_client_session(caching=True) as koji_api:
                    exectools.parallel_exec(lambda bug, _: self._find_latest_build(bug, koji_api), bugs,
                                            n_threads=BREW_POOL_SIZE)

            except Exception as e:
                self.logger.error(traceback.format_exc())
                self.logger.error(f'exception with {tracker.type} bug tracker: {e}')
                raise

        self._report_issues()

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
                return meta

        return None

    def _add_issue(self, bug, issue):
        if bug.id not in self.issues.keys():
            self.issues[bug.id] = []
        self.issues[bug.id].append(issue)

    def _report_issues(self):
        click.echo('==============================')

        if self.issues:
            click.echo('Found issues')
            click.echo(json.dumps(self.issues, indent=4))

        else:
            click.echo('No issues found')

        click.echo('==============================')

    def _find_latest_build(self, bug, koji_api):
        try:
            pscomponent = [keyword.split(':')[-1] for keyword in bug.keywords if 'pscomponent' in keyword][0]

        except IndexError:
            msg = f'bug {bug.id} does not have a pscomponent set'
            self.logger.warning(msg, bug.id)
            self._add_issue(bug, msg)
            return

        meta = self._find_meta_from_pscomponent(pscomponent)
        package_info = koji_api.getPackage(pscomponent)
        major, minor = isolate_major_minor_in_group(self.runtime.group)
        if meta:
            pattern = f'{pscomponent}*{major}.{minor}*.assembly.stream*'
        else:
            pattern = f'{pscomponent}*{major}.{minor}*'

        builds = koji_api.listBuilds(packageID=package_info['id'],
                                     state=BuildStates.COMPLETE.value,
                                     pattern=pattern,
                                     queryOpts={'limit': 1, 'order': '-creation_event_id'})
        if not builds:
            msg = f'No build found for {pscomponent} using pattern {pattern}'
            self.logger.warning(msg)
            self._add_issue(bug.id, msg)
            return

        latest_build = builds[0]
        self.logger.info(f'Found build for {pscomponent}: {latest_build["nvr"]}')
        return latest_build


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
