"""Interaction state, held in the user's record as a single tagged value.

`User.state` is exactly one of these, so an interaction in progress is one value
instead of several fields that can contradict each other — there is no way to
record "waiting for a secret" without also recording which platform and handle
it belongs to.

Adding a flow means adding a dataclass here and widening `State`; the handler
that owns the flow then switches on the concrete type.

The value is (de)serialized with pyserde's default external tagging, so the tag
is the class name: `{'AskingLoginHandle': {'platform': 'twitter'}}`. Renaming a
class therefore stops records written before the rename from loading.
"""

import serde

type State = (
    None
    # login
    | AskingLoginPlatform
    | AskingLoginHandle
    | AskingLoginSecret
    # logout
    | AskingLogoutAccount
    # forward
    | AskingForwardChat
)


@serde.serde
class AskingLoginPlatform:
    pass


@serde.serde
class AskingLoginHandle:
    platform: str = ''


@serde.serde
class AskingLoginSecret:
    platform: str = ''
    handle: str = ''


@serde.serde
class AskingLogoutAccount:
    pass


@serde.serde
class AskingForwardChat:
    pass
