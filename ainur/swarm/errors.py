__all__ = ['SwarmWarning', 'SwarmException', 'ConfigError']


class SwarmWarning(Warning):
    pass


class SwarmException(Exception):
    pass


# TODO: move somewhere else I guess.
class ConfigError(Exception):
    pass
