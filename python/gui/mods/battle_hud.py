# -*- coding: utf-8 -*-
"""
battle_hud.py — бойовий HUD для вибору пресету погоди.

Логіка:
  - Перше натискання F12 → відкривається HUD-меню (5 кнопок-пресетів).
  - Клавіші 1–5 або повторний F12 → вибір пресету і закриття HUD.
  - ESC або повторний F12 без вибору → закриття без змін.
  - HUD автоматично закривається через MENU_TIMEOUT секунд.
"""

import BigWorld
import Keys
from gui import SystemMessages

from weather_controller import (
    g_controller,
    PRESET_ORDER,
    PRESET_LABELS,
)

import logging
logger = logging.getLogger('weather_mod')

MENU_TIMEOUT = 6.0
PRESET_KEYS = [
    Keys.KEY_1,
    Keys.KEY_2,
    Keys.KEY_3,
    Keys.KEY_4,
    Keys.KEY_5,
]

_hud_active = False
_timeout_callback = None


def _cancel_timeout():
    global _timeout_callback
    if _timeout_callback is not None:
        try:
            BigWorld.cancelCallback(_timeout_callback)
        except Exception:
            pass
        _timeout_callback = None


def _show_menu():
    current = g_controller.getCurrentOverridePreset()
    lines = [u'[Weather] Оберіть пресет:']
    for i, preset_id in enumerate(PRESET_ORDER):
        label = PRESET_LABELS.get(preset_id, preset_id)
        marker = u' ◀' if preset_id == current else u''
        lines.append(u'  [%d] %s%s' % (i + 1, label, marker))
    lines.append(u'  [F12/ESC] Скасувати')
    msg = u'\n'.join(lines)
    try:
        SystemMessages.pushMessage(msg, SystemMessages.SM_TYPE.Information)
    except Exception:
        logger.exception('battle_hud._show_menu failed')


def open_hud():
    global _hud_active, _timeout_callback
    if _hud_active:
        close_hud()
        return
    _hud_active = True
    _show_menu()
    _cancel_timeout()
    _timeout_callback = BigWorld.callback(MENU_TIMEOUT, _on_timeout)
    logger.debug('battle_hud: opened')


def close_hud():
    global _hud_active
    _cancel_timeout()
    _hud_active = False
    logger.debug('battle_hud: closed')


def _on_timeout():
    global _hud_active, _timeout_callback
    _timeout_callback = None
    if _hud_active:
        _hud_active = False
        try:
            SystemMessages.pushMessage(
                u'[Weather] Меню закрито (таймаут)',
                SystemMessages.SM_TYPE.Information
            )
        except Exception:
            pass
        logger.debug('battle_hud: timeout closed')


def handle_key(key_code):
    """
    Обробник клавіш у бою.
    Повертає True якщо клавіша була «спожита» HUD-ом.
    """
    global _hud_active

    if not _hud_active:
        return False

    if key_code == Keys.KEY_ESCAPE:
        close_hud()
        return True

    if key_code == Keys.KEY_F12:
        close_hud()
        return True

    if key_code in PRESET_KEYS:
        idx = PRESET_KEYS.index(key_code)
        if idx < len(PRESET_ORDER):
            preset_id = PRESET_ORDER[idx]
            close_hud()
            # select_preset_in_battle існує в WeatherController v5.1
            g_controller.select_preset_in_battle(preset_id)
            return True

    return False


def is_active():
    return _hud_active
