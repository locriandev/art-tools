import json

import click
import requests

from doozerlib.cli import cli, pass_runtime

SERVER_URL = 'http://127.0.0.1:8000'  # Replace with your server's URL


@cli.command("images:list", help="List of distgits being selected.")
@pass_runtime
def images_list(runtime):
    result = requests.get(f'{SERVER_URL}/images/list?runtime_options=--group={runtime.group}')

    click.echo(f'Status code: {result.status_code}')
    click.echo(f'Response data:\n{json.dumps(result.json(), indent=4)}')


if __name__ == '__main__':
    cli()
