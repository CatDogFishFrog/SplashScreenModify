"""Application core: contracts, ports and module discovery.

This layer is pure: it has no console, file-system or third-party dependencies.
"""

from splashmodify.core.contracts import Action, ActionContext, Module, Target
from splashmodify.core.discovery import DiscoveryResult, LoadFailure, discover_modules
from splashmodify.core.errors import ActionError, OperationCancelled, SplashModifyError
from splashmodify.core.parameters import Arguments, Parameter, ParameterKind, collect_arguments
from splashmodify.core.ui import Prompter, Reporter, UserInterface

__all__ = [
    "Action",
    "ActionContext",
    "ActionError",
    "Arguments",
    "DiscoveryResult",
    "LoadFailure",
    "Module",
    "OperationCancelled",
    "Parameter",
    "ParameterKind",
    "Prompter",
    "Reporter",
    "SplashModifyError",
    "Target",
    "UserInterface",
    "collect_arguments",
    "discover_modules",
]
