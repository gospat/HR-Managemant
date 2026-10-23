"""
core/inherit/

Extension infrastructure for Horilla — model field injection and CBV replacement.

Key public symbols re-exported here for convenience:

    from core.inherit import HorillaViewInheritMixin   # view extension
    from core.inherit import HorillaModelBase           # model metaclass
    from core.inherit import INJECTION_MAP              # migration routing
    from core.inherit import VIEW_REGISTRY              # registered views
"""

from core.inherit.extension_registry import INJECTION_MAP
from core.inherit.model_inherit import EXTENSION_REGISTRY, HorillaModelBase
from core.inherit.view_inherit import HorillaViewInheritMixin
from core.inherit.view_registry import VIEW_REGISTRY

__all__ = [
    "HorillaViewInheritMixin",
    "HorillaModelBase",
    "INJECTION_MAP",
    "EXTENSION_REGISTRY",
    "VIEW_REGISTRY",
]
