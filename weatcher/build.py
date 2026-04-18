# -*- coding: utf-8 -*-
"""
build.py — збирає .wotmod з сирців.

Запуск:
    python build.py               # збирає версію з meta.xml
    python build.py --version 0.1.2   # форсує версію (використовується в CI на тегах)
    python build.py --skip-swf    # пропустити компіляцію SWF (якщо .swf уже є)
    python build.py --skip-pyc    # пропустити компіляцію .pyc (для швидкої ітерації)

Потребує:
    - Python 2.7 (для компіляції .pyc, що працюють у WoT)
    - Apache Flex SDK або AIR SDK (для mxmlc, компілятор AS3)
      Змінна оточення FLEX_HOME має вказувати на папку SDK.
    - WoT Scaleform SWC'и у as3/libs/
      (див. README.md — ці файли не комітяться, треба витягти з WoT-клієнта)

ВИХІД:
    dist/com.example.weather_<version>.wotmod
"""

from __future__ import print_function
import argparse
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile


# ---------------------------------------------------------------------------
# ШЛЯХИ ТА КОНСТАНТИ
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
AS3_SRC       = os.path.join(ROOT, "as3", "src")
AS3_LIBS      = os.path.join(ROOT, "as3", "libs")
PY_SRC        = os.path.join(ROOT, "python")
RES_TEMPLATE  = os.path.join(ROOT, "resources", "in", "mods")
DIST          = os.path.join(ROOT, "dist")

MOD_ID_DIR    = "com.example.weather"        # ім'я папки в res/mods/
SWF_NAME      = "WeatherMediator.swf"        # головний SWF (ім'я Mediator-класу)
MAIN_AS3_CLS  = "weather.WeatherMediator"    # fully-qualified клас-корінь


# ---------------------------------------------------------------------------
# Утиліти
# ---------------------------------------------------------------------------
def log(msg):
    print("[build] {}".format(msg))


def get_version_from_meta():
    """Читає <version> з meta.xml."""
    meta_path = os.path.join(RES_TEMPLATE, MOD_ID_DIR, "meta.xml")
    tree = ET.parse(meta_path)
    return tree.getroot().findtext("version", "0.0.1")


def patch_meta_version(staging_dir, version):
    """Підміняє версію в meta.xml всередині stage-папки (не чіпає оригінал)."""
    meta_path = os.path.join(staging_dir, "meta.xml")
    tree = ET.parse(meta_path)
    tree.getroot().find("version").text = version
    tree.write(meta_path, encoding="UTF-8", xml_declaration=True)


def find_flex_mxmlc():
    """Шукає mxmlc у FLEX_HOME або у PATH."""
    flex_home = os.environ.get("FLEX_HOME")
    if flex_home:
        candidate = os.path.join(flex_home, "bin",
                                 "mxmlc.bat" if os.name == "nt" else "mxmlc")
        if os.path.exists(candidate):
            return candidate
    # fallback — просто "mxmlc" якщо є в PATH
    return "mxmlc"


# ---------------------------------------------------------------------------
# Крок 1: компіляція AS3 → SWF
# ---------------------------------------------------------------------------
def compile_swf(output_swf):
    """Викликає mxmlc для збірки головного SWF."""
    log("Compiling SWF -> {}".format(output_swf))

    mxmlc = find_flex_mxmlc()

    # Основний .as файл (entry point). Flex знайде решту класів по package paths.
    main_as = os.path.join(AS3_SRC, "weather", "WeatherMediator.as")

    args = [
        mxmlc,
        main_as,
        "-output=" + output_swf,
        "-source-path=" + AS3_SRC,
        "-target-player=11.8",      # Scaleform GFx у WoT використовує AS3/Flash 11
        "-swf-version=21",
        "-static-link-runtime-shared-libraries=true",
        "-optimize=true",
        "-debug=false",
    ]

    # Підключаємо всі SWC з as3/libs/ (Scaleform CLIK + WoT framework)
    if os.path.isdir(AS3_LIBS):
        for fn in os.listdir(AS3_LIBS):
            if fn.endswith(".swc"):
                args.append("-library-path+=" + os.path.join(AS3_LIBS, fn))

    try:
        subprocess.check_call(args)
    except subprocess.CalledProcessError as e:
        log("ERROR: mxmlc failed with code {}".format(e.returncode))
        log("Check that FLEX_HOME is set and as3/libs/ contains WoT SWCs")
        sys.exit(1)
    except OSError as e:
        log("ERROR: mxmlc not found: {}".format(e))
        log("Install Apache Flex SDK and set FLEX_HOME env var")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Крок 2: компіляція Python → .pyc
# ---------------------------------------------------------------------------
def compile_python(src_dir, dst_dir):
    """
    Рекурсивно компілює всі .py з src_dir у .pyc в dst_dir.
    Зберігає відносні шляхи.

    ВАЖЛИВО: запускати цей скрипт треба на Python 2.7 — тільки такі .pyc
    зрозуміє WoT клієнт. На Python 3 magic number .pyc несумісний.
    """
    if sys.version_info[0] != 2:
        log("WARNING: running on Python {}.{} — WoT needs .pyc from Python 2.7!"
            .format(sys.version_info[0], sys.version_info[1]))
        log("         Скомпільовані .pyc, найімовірніше, не завантажаться у грі.")

    count = 0
    for dirpath, dirnames, filenames in os.walk(src_dir):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            src_file = os.path.join(dirpath, fn)
            rel = os.path.relpath(src_file, src_dir)
            dst_file = os.path.join(dst_dir, rel + "c")   # .py -> .pyc

            if not os.path.exists(os.path.dirname(dst_file)):
                os.makedirs(os.path.dirname(dst_file))

            py_compile.compile(src_file, dst_file, doraise=True)
            count += 1
    log("Compiled {} .py files".format(count))


# ---------------------------------------------------------------------------
# Крок 3: збірка .wotmod (zip з певною структурою)
# ---------------------------------------------------------------------------
def build_wotmod(staging_dir, version):
    """
    .wotmod = zip-архів з такою структурою:
        meta.xml
        res/
            scripts/client/gui/mods/*.pyc   <- наш Python
            mods/<author>.<mod>/            <- ресурси моду (swf, конфіги)
                gui/flash/WeatherMediator.swf
                configs/weather_mod.json
    """
    if not os.path.exists(DIST):
        os.makedirs(DIST)

    out_name = "{}_{}.wotmod".format(MOD_ID_DIR, version)
    out_path = os.path.join(DIST, out_name)

    log("Packing .wotmod -> {}".format(out_path))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _, filenames in os.walk(staging_dir):
            for fn in filenames:
                abs_path = os.path.join(dirpath, fn)
                rel_path = os.path.relpath(abs_path, staging_dir)
                # всередині zip розділювач завжди "/"
                zf.write(abs_path, rel_path.replace(os.sep, "/"))

    log("DONE. File size: {} bytes".format(os.path.getsize(out_path)))
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="override version from meta.xml")
    ap.add_argument("--skip-swf", action="store_true", help="skip AS3 compilation")
    ap.add_argument("--skip-pyc", action="store_true", help="skip .pyc compilation")
    args = ap.parse_args()

    version = args.version or get_version_from_meta()
    # Нормалізуємо: з git-тегу "v1.2.3" робимо "1.2.3"
    if version.startswith("v"):
        version = version[1:]
    log("Building version: {}".format(version))

    staging = tempfile.mkdtemp(prefix="wotmod_build_")
    log("Staging dir: {}".format(staging))

    try:
        # 1. Копіюємо шаблон з meta.xml, конфігами, іконками
        shutil.copytree(os.path.join(RES_TEMPLATE, MOD_ID_DIR),
                        os.path.join(staging, "res", "mods", MOD_ID_DIR))
        # meta.xml має лежати у корені архіву, а не в res/mods/
        shutil.move(os.path.join(staging, "res", "mods", MOD_ID_DIR, "meta.xml"),
                    os.path.join(staging, "meta.xml"))
        patch_meta_version(staging, version)

        # 2. AS3 → SWF
        swf_out = os.path.join(staging, "res", "mods", MOD_ID_DIR,
                               "gui", "flash", SWF_NAME)
        if args.skip_swf:
            log("Skipping SWF compilation")
        else:
            if not os.path.exists(os.path.dirname(swf_out)):
                os.makedirs(os.path.dirname(swf_out))
            compile_swf(swf_out)

        # 3. Python → .pyc
        pyc_out_dir = os.path.join(staging, "res", "scripts", "client", "gui", "mods")
        if args.skip_pyc:
            log("Skipping .pyc compilation")
            # Але покласти .py на випадок, якщо скрипти все одно потрібні
        else:
            compile_python(os.path.join(PY_SRC, "gui", "mods"), pyc_out_dir)

        # 4. Zip → .wotmod
        out = build_wotmod(staging, version)
        log("SUCCESS: {}".format(out))

    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
