"""Exceptions shared by the application and its modules."""


class SplashModifyError(Exception):
    """Base class for expected failures that are reported to the user."""


class ActionError(SplashModifyError):
    """An action could not be completed. The message is shown to the user as is."""


class OperationCancelled(SplashModifyError):
    """The user declined to continue, for example by leaving a prompt empty."""
