# -*- coding: utf-8 -*-

# Silent build: Weather mod must not write diagnostics into python.log.
# This runs before weather.controller / weather.window are imported.
try:
    import logging
    _logger = logging.getLogger('weather_mod')
    _logger.disabled = True
    _logger.propagate = False
    try:
        _logger.addHandler(logging.NullHandler())
    except Exception:
        pass
except Exception:
    pass
