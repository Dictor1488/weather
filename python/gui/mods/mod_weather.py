# -*- coding: utf-8 -*-
"""Explicit WoT mod entrypoint.

The main code lives in gui.mods.__init__. Some WoT loaders call init() only
on gui.mods.mod_* modules, so this file proxies lifecycle functions.

Note: onBecomePlayer / onBecomeNonPlayer etc. are NOT redefined here anymore.
The mod subscribes to g_playerEvents inside initialized() instead of exposing
top-level lifecycle functions, which avoids overwriting other mods' hooks.
"""

from gui.mods import initialized as _weather_initialized
from gui.mods import finalized as _weather_finalized
from gui.mods import handleKeyEvent as _weather_handleKeyEvent
from gui.mods import sendEvent as _weather_sendEvent


def init(*args, **kwargs):
    return _weather_initialized(*args, **kwargs)


def fini(*args, **kwargs):
    return _weather_finalized(*args, **kwargs)


def handleKeyEvent(event=None, *args, **kwargs):
    return _weather_handleKeyEvent(event, *args, **kwargs)


def sendEvent(*args, **kwargs):
    return _weather_sendEvent(*args, **kwargs)
