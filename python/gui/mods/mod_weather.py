# -*- coding: utf-8 -*-
"""Explicit WoT mod entrypoint.

The main code lives in gui.mods.__init__ for historical reasons. Some WoT
loaders call init() only on gui.mods.mod_* modules, so this file proxies the
standard lifecycle functions to the package-level implementation.
"""

from gui.mods import init as _weather_init
from gui.mods import fini as _weather_fini
from gui.mods import startGUI as _weather_startGUI
from gui.mods import destroyGUI as _weather_destroyGUI
from gui.mods import onAccountBecomePlayer as _weather_onAccountBecomePlayer
from gui.mods import onBecomePlayer as _weather_onBecomePlayer
from gui.mods import onBecomeNonPlayer as _weather_onBecomeNonPlayer
from gui.mods import onDisconnected as _weather_onDisconnected
from gui.mods import onConnected as _weather_onConnected
from gui.mods import handleKeyEvent as _weather_handleKeyEvent
from gui.mods import sendEvent as _weather_sendEvent


def init(*args, **kwargs):
    return _weather_init(*args, **kwargs)


def fini(*args, **kwargs):
    return _weather_fini(*args, **kwargs)


def startGUI(*args, **kwargs):
    return _weather_startGUI(*args, **kwargs)


def destroyGUI(*args, **kwargs):
    return _weather_destroyGUI(*args, **kwargs)


def onAccountBecomePlayer(*args, **kwargs):
    return _weather_onAccountBecomePlayer(*args, **kwargs)


def onBecomePlayer(*args, **kwargs):
    return _weather_onBecomePlayer(*args, **kwargs)


def onBecomeNonPlayer(*args, **kwargs):
    return _weather_onBecomeNonPlayer(*args, **kwargs)


def onDisconnected(*args, **kwargs):
    return _weather_onDisconnected(*args, **kwargs)


def onConnected(*args, **kwargs):
    return _weather_onConnected(*args, **kwargs)


def handleKeyEvent(event=None, *args, **kwargs):
    return _weather_handleKeyEvent(event, *args, **kwargs)


def sendEvent(*args, **kwargs):
    return _weather_sendEvent(*args, **kwargs)
