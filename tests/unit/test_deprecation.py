"""Tests for deprecation utilities."""

from __future__ import annotations

import warnings

from svc_infra.utils import (
    DeprecatedWarning,
    deprecated,
    deprecated_parameter,
)


class TestDeprecatedDecorator:
    """Tests for the @deprecated decorator."""

    def test_deprecated_function_emits_warning(self):
        """Test that deprecated function emits DeprecationWarning."""

        @deprecated(version="1.0.0", reason="Use new_func() instead", removal_version="1.2.0")
        def old_func():
            return "result"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_func()

            assert result == "result"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecatedWarning)
            assert "old_func is deprecated since version 1.0.0" in str(w[0].message)
            assert "Use new_func() instead" in str(w[0].message)
            assert "removed in version 1.2.0" in str(w[0].message)

    def test_deprecated_function_without_removal_version(self):
        """Test deprecated function without removal version."""

        @deprecated(version="1.0.0", reason="Use new_func() instead")
        def old_func():
            return "result"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_func()

            assert len(w) == 1
            assert "removed in version" not in str(w[0].message)

    def test_deprecated_function_preserves_metadata(self):
        """Test that decorated function preserves original metadata."""

        @deprecated(version="1.0.0", reason="Test")
        def documented_func():
            """Original docstring."""
            return "result"

        assert "deprecated:: 1.0.0" in documented_func.__doc__
        assert "Original docstring" in documented_func.__doc__
        assert documented_func.__name__ == "documented_func"

    def test_deprecated_class_emits_warning(self):
        """Test that deprecated class emits warning on instantiation."""

        @deprecated(version="1.0.0", reason="Use NewClass instead", removal_version="1.2.0")
        class OldClass:
            def __init__(self, value: int):
                self.value = value

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            instance = OldClass(42)

            assert instance.value == 42
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecatedWarning)
            assert "OldClass is deprecated" in str(w[0].message)

    def test_deprecated_function_with_args(self):
        """Test deprecated function with arguments."""

        @deprecated(version="1.0.0", reason="Test")
        def add(a: int, b: int) -> int:
            return a + b

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = add(1, 2)

            assert result == 3
            assert len(w) == 1

    def test_deprecated_function_with_kwargs(self):
        """Test deprecated function with keyword arguments."""

        @deprecated(version="1.0.0", reason="Test")
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = greet("World", greeting="Hi")

            assert result == "Hi, World!"
            assert len(w) == 1


class TestDeprecatedParameter:
    """Tests for deprecated_parameter function."""

    def test_deprecated_parameter_emits_warning(self):
        """Test that deprecated parameter emits warning."""

        def my_func(new_param: str, old_param: str | None = None) -> str:
            if old_param is not None:
                deprecated_parameter(
                    name="old_param",
                    version="1.0.0",
                    reason="Use new_param instead",
                    removal_version="1.2.0",
                )
                new_param = old_param
            return new_param

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = my_func(new_param="test", old_param="deprecated")

            assert result == "deprecated"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecatedWarning)
            assert "old_param" in str(w[0].message)
            assert "deprecated since version 1.0.0" in str(w[0].message)

    def test_deprecated_parameter_no_warning_when_not_used(self):
        """Test that no warning is emitted when deprecated param not used."""

        def my_func(new_param: str, old_param: str | None = None) -> str:
            if old_param is not None:
                deprecated_parameter(
                    name="old_param", version="1.0.0", reason="Use new_param instead"
                )
                new_param = old_param
            return new_param

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = my_func(new_param="test")

            assert result == "test"
            assert len(w) == 0

    def test_deprecated_parameter_without_removal_version(self):
        """Test deprecated parameter without removal version."""

        def my_func(old_param: str | None = None) -> str:
            if old_param is not None:
                deprecated_parameter(name="old_param", version="1.0.0", reason="Use new approach")
            return old_param or "default"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            my_func(old_param="test")

            assert len(w) == 1
            assert "removed in version" not in str(w[0].message)


class TestDeprecatedWarningClass:
    """Tests for DeprecatedWarning class."""

    def test_deprecated_warning_is_deprecation_warning(self):
        """Test that DeprecatedWarning is a DeprecationWarning subclass."""
        assert issubclass(DeprecatedWarning, DeprecationWarning)

    def test_can_filter_deprecated_warning(self):
        """Test that DeprecatedWarning can be filtered specifically."""

        @deprecated(version="1.0.0", reason="Test")
        def old_func():
            pass

        # Filter only DeprecatedWarning
        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings("ignore", category=DeprecatedWarning)
            old_func()

            # Warning should be filtered out
            assert len(w) == 0
