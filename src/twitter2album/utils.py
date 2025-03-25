from inspect import currentframe, getframeinfo
from types import EllipsisType, NoneType
from typing import Any, Mapping

from prettyprinter import cpprint
from prettyprinter.prettyprinter import (
    PrettyContext,
    is_registered,
    pretty_call,
    pretty_python_value,
    register_pretty,
)


def dbg(value, depth=2):
    caller = getframeinfo(currentframe().f_back)
    print(f'{caller.filename}:{caller.lineno}')
    cpprint(DebugWrapper(value), depth=depth)

    return value


class DebugWrapper:
    def __init__(self, value: Any):
        self.value = value
        self.ctor = type(value)

    def is_primitive(self):
        return isinstance(self.value, (bool, str, int, float, NoneType, EllipsisType))

    def is_basic(self):
        return isinstance(self.value, (type, slice, range))

    def is_sequence(self):
        return isinstance(self.value, (list, tuple, set, frozenset))

    def is_mapping(self):
        return isinstance(self.value, Mapping)

    def is_object(self):
        return isinstance(self.value, object) and hasattr(self.value, '__dict__')

    def is_trivial(self):
        if self.is_primitive() or self.is_basic():
            return True
        if self.is_sequence() or self.is_mapping() or self.is_object():
            return False
        return is_registered(type(self.value), check_superclasses=True)


@register_pretty(DebugWrapper)
def pretty_debug(wrapper: DebugWrapper, ctx: PrettyContext):
    if wrapper.is_primitive():
        return pretty_python_value(wrapper.value, relax_once(ctx, 'primitive'))

    if wrapper.is_trivial():
        return pretty_python_value(wrapper.value, ctx)

    if wrapper.is_sequence():
        items = [DebugWrapper(item) for item in wrapper.value]
        items = wrapper.ctor(items)
        return pretty_python_value(items, relax_once(ctx, 'sequence'))

    if wrapper.is_mapping():
        fields = {key: DebugWrapper(item)
                  for key, item in wrapper.value.items()}
        return pretty_python_value(fields, ctx)

    if wrapper.is_object():
        fields = {key: DebugWrapper(item)
                  for key, item in vars(wrapper.value).items()}
        return pretty_call(ctx, wrapper.ctor, **fields)

    return pretty_call(ctx, wrapper.ctor, wrapper.value)


def relax_once(ctx: PrettyContext, key: str):
    if ctx.depth_left > 0 or ctx.get(key, False):
        return ctx
    return ctx.assoc(key, True)._replace(depth_left=ctx.depth_left + 1)
