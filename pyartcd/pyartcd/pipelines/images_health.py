import click
from artcommonlib import exectools
from pyartcd import util
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime


class ImagesHealthPipeline:
    def __init__(self, runtime: Runtime, version: str,
                 send_to_release_channel: bool, send_to_forum_ocp_art: bool):
        self.runtime = runtime
        self.doozer_working = self.runtime.working_dir / "doozer_working"
        self.logger = self.runtime.logger
        self.version = version
        self.send_to_release_channel = send_to_release_channel
        self.send_to_forum_ocp_art = send_to_forum_ocp_art
        self.report = ''
        self.slack_client = None

    async def run(self):
        # Check if automation is frozen for current group
        if not await util.is_build_permitted(self.version, doozer_working=self.doozer_working):
            self.logger.info('Skipping this build as it\'s not permitted')
            return

        # Get doozer report
        cmd = [
            'doozer',
            f'--working-dir={self.doozer_working}',
            f'--group=openshift-{self.version}',
            'images:health'
        ]
        _, out, err = await exectools.cmd_gather_async(cmd)
        self.report = out.strip()
        if self.report:
            self.logger.info('images:health output for openshift-%s:\n%s', self.version, out)

        if any([self.send_to_release_channel, self.send_to_forum_ocp_art]):
            self.slack_client = self.runtime.new_slack_client()
            await self._send_notifications()

    async def _send_notifications(self):
        if self.report:
            count = self.report.count('Latest attempt')
            msg = f':alert: Howdy! There are some issues to look into for openshift-{self.version}. {count} components have failed!'

            if self.send_to_release_channel:
                self.slack_client.bind_channel(self.version)
                response = await self.slack_client.say(msg)
                await self.slack_client.say(f'{self.report}', thread_ts=response['ts'])

            if self.send_to_forum_ocp_art:
                self.slack_client.bind_channel('#forum-ocp-art')
                response = await self.slack_client.say(msg)
                await self.slack_client.say(f'{self.report}', thread_ts=response['ts'])

        else:
            if self.send_to_release_channel:
                self.slack_client.bind_channel(self.version)
                await self.slack_client.say(f':white_check_mark: All images are healthy for openshift-{self.version}')


@cli.command('images-health')
@click.option('--version', required=True, help='OCP version to scan')
@click.option('--send-to-release-channel', is_flag=True,
              help='If true, send output to #art-release-4-<version>')
@click.option('--send-to-forum-ocp-art', is_flag=True,
              help='"If true, send notification to #forum-ocp-art')
@pass_runtime
@click_coroutine
async def images_health(runtime: Runtime, version: str, send_to_release_channel: bool, send_to_forum_ocp_art: bool):
    await ImagesHealthPipeline(runtime, version, send_to_release_channel, send_to_forum_ocp_art).run()
