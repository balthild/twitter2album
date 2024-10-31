from inspect import currentframe, getframeinfo
from prettyprinter import cpprint, pretty_call, register_pretty


def dbg(value):
    caller = getframeinfo(currentframe().f_back)
    print(f'{caller.filename}:{caller.lineno}')

    cpprint(_DebugClass.serialize(value))

    return value


class _DebugClass:
    def __init__(self, type, value):
        self.type = type
        self.value = value

    def serialize(value):
        if isinstance(value, list):
            return [_DebugClass.serialize(x) for x in value]

        if not hasattr(value, '__dict__'):
            return value

        fields = {}
        for key in value.__dict__:
            fields[key] = _DebugClass.serialize(value.__dict__[key])

        return _DebugClass(type(value), fields)


@register_pretty(_DebugClass)
def _print_debug_class(value: _DebugClass, ctx):
    return pretty_call(ctx, value.type, value.value)
