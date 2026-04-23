"""
Shared test utilities and base classes for the shared/ library tests.
"""

import logging
import unittest

from shared.src.singleton.singleton import SingletonMeta


class SharedTestBase(unittest.TestCase):
    """
    Base class for all shared/ library tests.

    Handles singleton registry reset between tests so that EDHLogger (and any
    other singleton) does not bleed state across test methods.
    """

    def setUp(self) -> None:
        SingletonMeta._instances.clear()
        # Remove any handlers attached to the root logger during previous tests
        root = logging.getLogger()
        root.handlers.clear()

    def tearDown(self) -> None:
        SingletonMeta._instances.clear()
        root = logging.getLogger()
        root.handlers.clear()
