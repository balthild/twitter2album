class AbortException(Exception):
    pass


class UserException(Exception):
    pass


class StateException(Exception):
    def __init__(self, command: str | None = None):
        if command is None:
            super().__init__('Invalid state. Please start over')
        else:
            super().__init__(f'Invalid state. Please run `{command}` again')
