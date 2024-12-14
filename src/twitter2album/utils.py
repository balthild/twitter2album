from inspect import currentframe, getframeinfo
from prettyprinter import cpprint, pretty_call, register_pretty


def dbg(value):
    caller = getframeinfo(currentframe().f_back)
    print(f'{caller.filename}:{caller.lineno}')

    cpprint(DebugClass.serialize(value))

    return value


class DebugClass:
    def __init__(self, type, value):
        self.type = type
        self.value = value

    def serialize(value, depth=0):
        if depth > 4:
            return DebugClass(type(value), '...')

        if isinstance(value, list):
            return [DebugClass.serialize(x, depth+1) for x in value]

        if not hasattr(value, '__dict__'):
            return value

        fields = {}
        for key in value.__dict__:
            fields[key] = DebugClass.serialize(value.__dict__[key], depth+1)

        return DebugClass(type(value), fields)


@register_pretty(DebugClass)
def print_debug_class(value: DebugClass, ctx):
    return pretty_call(ctx, value.type, value.value)
