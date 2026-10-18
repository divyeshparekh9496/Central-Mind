"""Service exports are lazy so offline retrieval does not require cloud SDKs."""
from importlib import import_module

_EXPORTS = {'SemanticCache': 'semantic_cache', 'FactChecker': 'fact_checker',
            'WebSearchService': 'web_search', 'ResearchAgent': 'research_agent'}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(f'{__name__}.{_EXPORTS[name]}'), name)
    globals()[name] = value
    return value
