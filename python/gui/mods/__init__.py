# -*- coding: utf-8 -*-
# Маркер пакета gui.mods + повний набір заглушок WoT mod loader API.
# WoT перебирає всі .py файли в gui/mods/ і викликає у кожному:
#   init(), fini(), sendEvent(), onHangarSpaceCreate(), onHangarSpaceDestroy()
# Якщо якоїсь функції немає — клієнт падає з AttributeError.


def init():
    pass


def fini():
    pass


def sendEvent(*args, **kwargs):
    pass


def onHangarSpaceCreate(*args, **kwargs):
    pass


def onHangarSpaceDestroy(*args, **kwargs):
    pass
