"""Optional third-party packages the suite can use, and how a missing one is reported.

The standard library runs most of the suite. A few test files drive the
art/sprite tooling and need numpy, jsonschema or Pillow
(`pip install -r scripts/tests/requirements.txt`). Without one of those, the
tests that need it skip and a line on stderr names the package and the file;
nothing errors on import.

    import _deps
    _deps.require("PIL", "jsonschema")   # top of a file: skip the whole file

    @_deps.needs("PIL")                  # on a TestCase class or a test method
"""
import importlib.util
import os
import sys
import unittest

HINT = "pip install -r scripts/tests/requirements.txt"
_announced = set()


def missing(*modules):
    return [m for m in modules if importlib.util.find_spec(m) is None]


def _reason(gone):
    return "needs %s (not installed; %s)" % (", ".join(gone), HINT)


def _announce(gone, frame):
    where = os.path.basename(frame.f_globals.get("__file__", "?"))
    key = (tuple(gone), where)
    if key not in _announced:
        _announced.add(key)
        print("SKIP %s: %s" % (where, _reason(gone)), file=sys.stderr)


def require(*modules):
    """Skip the calling test module when any of `modules` is not installed."""
    gone = missing(*modules)
    if gone:
        _announce(gone, sys._getframe(1))
        raise unittest.SkipTest(_reason(gone))


def needs(*modules):
    """Decorator: skip a TestCase class or test method when `modules` are not installed."""
    gone = missing(*modules)
    if gone:
        _announce(gone, sys._getframe(1))
    return unittest.skipIf(bool(gone), _reason(gone))
