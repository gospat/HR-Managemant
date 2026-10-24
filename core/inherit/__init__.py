"""
core/inherit/

Extension infrastructure for Bells Tech — model field injection and CBV replacement.

Key public symbols re-exported here for convenience:

    from core.inherit import HrViewInheritMixin   # view extension
    from core.inherit import HrModelBase           # model metaclass
    from core.inherit import INJECTION_MAP              # migration routing
    from core.inherit import VIEW_REGISTRY              # registered views
"""

from core.inherit.extension_registry import INJECTION_MAP
from core.inherit.model_inherit import EXTENSION_REGISTRY, HrModelBase
from core.inherit.view_inherit import HrViewInheritMixin
from core.inherit.view_registry import VIEW_REGISTRY

__all__ = [
    "HrViewInheritMixin",
    "HrModelBase",
    "INJECTION_MAP",
    "EXTENSION_REGISTRY",
    "VIEW_REGISTRY",
]
