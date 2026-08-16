from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

try:  # Streamlit is available in the dashboard runtime.
    import streamlit as st
except ModuleNotFoundError:  # Allows non-UI scripts/tests to import data modules.
    st = None  # type: ignore[assignment]


def cache_data(*args: Any, **kwargs: Any):
    """Use st.cache_data in Streamlit, otherwise behave like a no-op decorator."""
    if st is not None:
        return st.cache_data(*args, **kwargs)

    if args and callable(args[0]) and len(args) == 1 and not kwargs:
        return args[0]

    def decorator(func: F) -> F:
        return func

    return decorator
