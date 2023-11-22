import logging
from collections import OrderedDict

import click
import makefun
import uvicorn
from fastapi import FastAPI

from doozerlib import exectools
from doozerlib.cli import cli
from doozerlib.cli import __main__


class ApiServer(FastAPI):
    def __init__(self, cli_name):
        super().__init__()

        self.logger = None
        self.cli_name = cli_name
        self.cli_commands = {}

        self.initialize()

    def initialize(self):
        self.initialize_logger()
        self.add_routes()

    def initialize_logger(self):
        default_log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

        # Root logger setup
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARN)
        root_stream_handler = logging.StreamHandler()
        root_stream_handler.setFormatter(default_log_formatter)
        root_logger.addHandler(root_stream_handler)

        # ApiServer setup
        self.logger = logging.getLogger(__name__)
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG)

        main_stream_handler = logging.StreamHandler()
        main_stream_handler.setFormatter(default_log_formatter)
        main_stream_handler.setLevel(logging.INFO)
        self.logger.addHandler(main_stream_handler)

    @staticmethod
    def generate_endpoint_name(cli_command_name):
        return f"/{cli_command_name.replace('-', '_').replace(':', '/')}"

    @staticmethod
    def generate_handler_name(cli_command):
        return cli_command.name.replace('-', '_').replace(':', '_')

    def generate_handler_signature(self, cli_command):
        # TODO params of type Argument are ignored

        command_options = [
            self.convert_click_option_to_fastapi_param(param) for param in cli_command.params if
            isinstance(param, click.Option)
        ]

        param_signatures = []
        for param in command_options:
            signature = f'{param["name"]}: {param["type"]}=None'
            param_signatures.append(signature)

        return f'{self.generate_handler_name(cli_command)}(runtime_options: str, {", ".join(param_signatures)})'

    @staticmethod
    def convert_click_option_to_fastapi_param(option):
        """
        Depending on the option type (text, int, etc.), define FastAPI parameter type
        """

        if type(option.type) == click.types.StringParamType:
            param_type = 'str'
        elif type(option.type) == click.types.BoolParamType:
            param_type = 'bool'
        elif type(option.type) == click.types.IntParamType:
            param_type = 'int'
        elif type(option.type) == click.types.Choice:
            param_type = 'str'
        else:
            raise RuntimeError(f'Unexpected param type "{type(option.type)}" for param {option.name}')

        return {'name': option.name, 'type': param_type, 'help': option.help, 'default': option.default}

    def generate_route_docs(self, command):
        docs = f'<h2>{self.cli_name} {command.name}</h2>'
        docs += f'<br><br>{command.short_help}'
        if command.help:
            docs += f'<br><br>{command.help}'
        return docs

    def parse_commands(self, cli_group: click.core.Group, command_map: dict, prefix=''):
        for command_name, command_obj in cli_group.commands.items():
            if type(command_obj) == click.core.Command:
                command_map[f'{prefix}{command_name}'] = command_obj

            elif type(command_obj) == click.core.Group:
                self.parse_commands(command_obj, command_map, prefix=f'{command_obj.name}:')

            else:
                raise ValueError(f'Unexpected type for command {command_obj.name}')

    def add_routes(self):
        self.parse_commands(cli, self.cli_commands)

        # Let's have the routes sorted alphabetically
        sorted_commands = OrderedDict(sorted(self.cli_commands.items()))

        for command_name, command in sorted_commands.items():
            handler_signature = self.generate_handler_signature(command)
            self.logger.debug('Adding route at %s for command %s', handler_signature, command_name)

            def wrapper(name):
                def wrapped(*_, **kwargs):
                    try:
                        # Parse options given to the runtime
                        runtime_options = kwargs.pop('runtime_options', '')

                        # Parse options given to the command
                        options_map = {param.name: param for param in self.cli_commands[name].params
                                       if kwargs.get(param.name, None)}

                        command_options = []
                        for k, v in kwargs.items():
                            if k not in options_map:
                                continue
                            param = options_map[k]
                            if type(param.type) == click.types.BoolParamType:
                                command_options.append(param.opts[0])
                            elif type(param.type) == click.types.StringParamType and v:
                                command_options.append(f'{param.opts[0]}={v}')
                            else:
                                command_options.append(f'{param.opts[0]}={v}')

                        # Build CLI command with all the required options
                        cmd = [self.cli_name]
                        cmd.extend(runtime_options.strip().split())
                        cmd.append(name)
                        cmd.extend(command_options)
                        self.logger.info('Executing command: %s', ' '.join(cmd))
                        rc, stdout, stderr = exectools.cmd_gather(cmd)
                        return {'status': 'success', 'rc': rc, 'command': ' '.join(cmd), 'output': stdout, 'stderr': stderr}

                    except Exception as e:
                        return {'status': 'failure', 'command': name, 'error': str(e)}

                wrapped.__doc__ = self.generate_route_docs(command)

                try:
                    handler = makefun.create_function(handler_signature, wrapped)

                except Exception as e:
                    self.logger.error('Failed generating route for command %s: %s', command.name, e)
                    raise

                return handler

            self.add_api_route(self.generate_endpoint_name(command_name), wrapper(command.name))


if __name__ == "__main__":
    uvicorn.run(ApiServer('doozer'), host="0.0.0.0", port=8000)
