"""
Custom exceptions for turbo-orm.
"""


class TurboOrmError(Exception):
    """Base exception for all turbo-orm errors."""

    pass


class EmptyResultSet(TurboOrmError):
    """Query returned no results when one was expected."""

    pass
