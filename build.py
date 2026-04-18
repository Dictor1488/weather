# SPDX-License-Identifier: MIT

"""
Build script for creating and packaging World of Tanks modifications.

This script handles:
- Compiling Python scripts with Python 2.7.
- Publishing Adobe Animate projects.
- Packaging mod files into a .wotmod archive.
- Creating a distributable .zip archive.
- Copying the mod to the game directory and running the game.
"""

import argparse
import datetime
import json
import logging
import os
import pathlib
import random
import shutil
import string
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional, Set

try:
    import psutil
except ImportError:
    raise ImportError("psutil is not installed. Please run 'pip install psutil' to install it.")


class ElapsedFormatter(logging.Formatter):
    """A logging formatter that includes the elapsed time since initialization."""

    def __init__(self) -> None:
        super().__init__()
        self.start_time = time.time()

    def format(self, record: logging.LogRecord) -> str:
        elapsed_seconds = record.created - self.start_time
        elapsed = datetime.timedelta(seconds=elapsed_seconds)
        return f"{elapsed.seconds:03d}.{int(elapsed.microseconds / 1000):03d} {record.getMessage()}"


def setup_logger() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(ElapsedFormatter())

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.handlers = []
    logger.addHandler(handler)
    return logger


class AppConfig:
    """A class to hold the application configuration from build.json."""

    class Software:
        def __init__(self, data: Dict[str, Any]) -> None:
            self.animate: Optional[str] = data.get("animate")
            self.python: Optional[str] = data.get("python")

    class Game:
        def __init__(self, data: Dict[str, Any]) -> None:
            self.force: bool = data.get("force", False)
            self.folder: Optional[str] = data.get("folder")
            self.version: Optional[str] = data.get("version")

    class Info:
        def __init__(self, data: Dict[str, Any]) -> None:
            self.id: Optional[str] = data.get("id")
            self.name: Optional[str] = data.get("name")
            self.description: Optional[str] = data.get("description")
            self.version: Optional[str] = data.get("version")

    def __init__(self, data: Dict[str, Any]) -> None:
        self.version: int = data.get("version", 0)
        self.software = self.Software(data.get("software", {}))
        self.game = self.Game(data.get("game", {}))
        self.info = self.Info(data.get("info", {}))


def rand_str(num: int) -> str:
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(num))


def copytree(source: str, destination: str, ignore: Optional[callable] = None) -> None:
    source_path = pathlib.Path(source)
    dest_path = pathlib.Path(destination)
    dest_path.mkdir(parents=True, exist_ok=True)

    names = os.listdir(str(source_path))
    ignored_names: Set[str] = ignore(str(source_path), names) if ignore else set()

    for name in names:
        if name in ignored_names or ".gitkeep" in name:
            continue

        srcname = source_path / name
        dstname = dest_path / name

        try:
            if srcname.is_dir():
                copytree(str(srcname), str(dstname), ignore)
            else:
                shutil.copy2(str(srcname), str(dstname))
        except (IOError, OSError) as why:
            logger.error("Can't copy %s to %s: %s", srcname, dstname, str(why))


def zip_folder(source: str, destination: str, mode: str = "w", compression: int = zipfile.ZIP_STORED) -> None:
    source_path = pathlib.Path(source)
    with zipfile.ZipFile(destination, mode, compression) as zipfh:
        now = tuple(datetime.datetime.now().timetuple())[:6]
        for file_path in source_path.rglob("*"):
            arcname = file_path.relative_to(source_path)
            arcname_str = str(arcname).replace("\\", "/")

            if file_path.is_dir():
                info = zipfile.ZipInfo(arcname_str + "/", now)
                info.compress_type = compression
                zipfh.writestr(info, "")
            else:
                info = zipfile.ZipInfo(arcname_str, now)
                info.external_attr = 33206 << 16  # -rw-rw-rw-
                info.compress_type = compression
                zipfh.writestr(info, file_path.read_bytes())


def is_process_running(path: str) -> bool:
    process_name = pathlib.Path(path).name.lower()
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name == process_name:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False


def build_flash(config: AppConfig, args: argparse.Namespace) -> None:
    if not args.flash:
        return

    files_to_process = list(pathlib.Path("as3").rglob("*.fla")) + list(pathlib.Path("as3").rglob("*.xfl"))
    if not files_to_process:
        logger.info("No Flash files found to build.")
        return

    if not config.software.animate or not is_process_running(config.software.animate):
        raise Exception("Adobe Animate is not running or not configured in build.json.")

    for file_path in files_to_process:
        log_path = file_path.with_suffix(".log")
        jsfl_file = pathlib.Path("build-{}.jsfl".format(rand_str(5)))
        document_uri = file_path.resolve().as_uri()
        log_file_uri = log_path.resolve().as_uri()

        jsfl_content = 'fl.publishDocument("{}", "Default");\n'.format(document_uri)
        jsfl_content += 'fl.compilerErrors.save("{}", false, true);\n'.format(log_file_uri)
        jsfl_file.write_text(jsfl_content, encoding="utf-8")

        try:
            subprocess.check_call(
                [config.software.animate, "-e", str(jsfl_file), "-AlwaysRunJSFL"],
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError:
            logger.exception("build_flash failed for %s", file_path)
            raise

        while jsfl_file.exists():
            try:
                jsfl_file.unlink()
            except OSError:
                time.sleep(0.01)

        log_data = ""
        if log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if len(lines) > 1:
                log_data = "\n".join(lines[:-2])
            log_path.unlink()

        if log_data:
            raise RuntimeError("Failed flash publish {}\n{}".format(file_path, log_data))
        else:
            logger.info("Flash published: %s", file_path)


def build_python(config: AppConfig) -> None:
    """
    Compiles all .py files into .pyc bytecode using Python 2.7.
    Fails the build if at least one file did not compile.
    """
    python_source_dir = pathlib.Path("python")
    if not python_source_dir.is_dir():
        logger.info("No python directory found, skipping Python compilation.")
        return

    if not config.software.python:
        raise ValueError("Python executable path is not configured in build.json")

    py2_path = pathlib.Path(config.software.python)
    if not py2_path.is_file():
        raise FileNotFoundError("Configured Python 2 executable not found: {}".format(config.software.python))

    failed_files: List[str] = []
    compiled_count = 0

    for file_path in python_source_dir.rglob("*.py"):
        try:
            output = subprocess.check_output(
                [config.software.python, "-m", "py_compile", str(file_path)],
                stderr=subprocess.STDOUT,
            )
            if output:
                try:
                    logger.info(output.decode("utf-8", errors="ignore").strip())
                except Exception:
                    pass

            pyc_path = file_path.with_suffix(".pyc")
            if not pyc_path.is_file():
                failed_files.append("{} (py_compile returned success, but .pyc not found)".format(file_path))
                logger.error("Python fail compile: %s\nCompiled successfully, but .pyc not found", file_path)
                continue

            compiled_count += 1
            logger.info("Python compiled: %s -> %s", file_path, pyc_path)

        except subprocess.CalledProcessError as e:
            try:
                error_output = e.output.decode("utf-8", errors="ignore")
            except Exception:
                error_output = str(e.output)

            logger.error("Python fail compile: %s\n%s", file_path, error_output)
            failed_files.append(str(file_path))

    logger.info("Python compilation finished. Compiled: %d", compiled_count)

    if failed_files:
        raise RuntimeError(
            "Python compilation failed for {} file(s):\n{}".format(
                len(failed_files),
                "\n".join(failed_files),
            )
        )


def indent_xml(root: ET.Element) -> None:
    """
    Compatible XML indentation for Python versions where ET.indent may be unavailable.
    """
    try:
        ET.indent(root, space="    ")
        return
    except AttributeError:
        pass

    def _indent(elem: ET.Element, level: int = 0) -> None:
        i = "\n" + level * "    "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "    "
            for child in elem:
                _indent(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    _indent(root)


def safe_unlink(path: pathlib.Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except FileNotFoundError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Build script for WoT mods.")
    parser.add_argument("--flash", action="store_true", help="Build flash assets.")
    parser.add_argument("--ingame", action="store_true", help="Copy the build into the game directory.")
    parser.add_argument("--distribute", action="store_true", help="Create a distributable archive.")
    parser.add_argument("--run", action="store_true", help="Run the game after a successful build.")
    args = parser.parse_args()

    config_path = pathlib.Path("build.json")
    if not config_path.is_file():
        raise FileNotFoundError("Config not found: build.json")

    with config_path.open("r", encoding="utf-8") as fh:
        config_data = json.load(fh)
        config = AppConfig(config_data)

    if config.game.force:
        game_folder = pathlib.Path(config.game.folder) if config.game.folder else None
        game_version = config.game.version
    else:
        game_folder_env = os.environ.get("WOT_FOLDER", config.game.folder or "")
        game_version = os.environ.get("WOT_VERSION", config.game.version or "")
        game_folder = pathlib.Path(game_folder_env) if game_folder_env else None

    if args.ingame or args.run:
        if not game_folder or not game_version:
            raise ValueError("Game folder or version is not configured for --ingame/--run.")

    temp_dir = pathlib.Path("temp")
    build_dir = pathlib.Path("build")

    if temp_dir.is_dir():
        shutil.rmtree(str(temp_dir))
    temp_dir.mkdir()

    if build_dir.is_dir():
        shutil.rmtree(str(build_dir))
    build_dir.mkdir()

    logger.info("Starting build process...")
    build_python(config)
    build_flash(config, args)

    logger.info("Packaging mod...")
    package_name = "{}_{}.wotmod".format(config.info.id, config.info.version)

    root = ET.Element("root")
    ET.SubElement(root, "id").text = config.info.id
    ET.SubElement(root, "version").text = config.info.version
    ET.SubElement(root, "name").text = config.info.name
    ET.SubElement(root, "description").text = config.info.description

    indent_xml(root)
    meta_content = ET.tostring(root, encoding="unicode")

    if pathlib.Path("resources/in").is_dir():
        copytree("resources/in", str(temp_dir / "res"))
    if pathlib.Path("as3/bin").is_dir():
        copytree("as3/bin", str(temp_dir / "res/gui/flash"))

    copytree("python", str(temp_dir / "res/scripts/client"), ignore=shutil.ignore_patterns("*.py"))
    (temp_dir / "meta.xml").write_text(meta_content, encoding="utf-8")

    zip_folder(str(temp_dir), str(build_dir / package_name))
    logger.info("Package created: %s", build_dir / package_name)

    if args.ingame:
        wot_packages_dir = game_folder / "mods" / game_version
        if not wot_packages_dir.is_dir():
            raise FileNotFoundError("WoT mods folder not found: {}".format(wot_packages_dir))

        exe_name = "worldoftanks.exe"
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                proc_name = (proc.info.get("name") or "").lower()
                if exe_name in proc_name:
                    p = psutil.Process(proc.info["pid"])
                    p.terminate()
                    logger.info("WoT client closing (pid: %s)", proc.info["pid"])
                    p.wait(timeout=10)
            except (psutil.Error, KeyError) as e:
                logger.warning("Could not terminate WoT client: %s", e)

        logger.info("Copying package to: %s", wot_packages_dir / package_name)
        shutil.copy2(str(build_dir / package_name), str(wot_packages_dir))

    if args.distribute:
        if not game_version:
            raise ValueError("Game version is not configured for --distribute.")

        logger.info("Creating distribution archive...")
        dist_dir = temp_dir / "distribute"
        dist_mods_dir = dist_dir / "mods" / game_version
        dist_mods_dir.mkdir(parents=True)

        shutil.copy2(str(build_dir / package_name), str(dist_mods_dir))
        if pathlib.Path("resources/out").is_dir():
            copytree("resources/out", str(dist_dir))

        zip_name = "{}_{}.zip".format(config.info.id, config.info.version)
        zip_folder(str(dist_dir), str(build_dir / zip_name))
        logger.info("Distribution archive created: %s", build_dir / zip_name)

    logger.info("Cleaning up temporary files...")
    cleanup_paths: List[pathlib.Path] = [
        temp_dir,
        pathlib.Path("EvalScript error.tmp"),
        pathlib.Path("as3/DataStore"),
    ]
    cleanup_paths.extend(pathlib.Path("python").rglob("*.pyc"))

    for path in cleanup_paths:
        if path.is_dir():
            shutil.rmtree(str(path), ignore_errors=True)
        elif path.is_file():
            safe_unlink(path)

    if args.run:
        executable_path = game_folder / "worldoftanks.exe"
        if executable_path.is_file():
            logger.info("Starting World of Tanks client...")
            subprocess.Popen([str(executable_path)])
        else:
            logger.warning("Could not find game executable to run at: %s", executable_path)

    logger.info("Build finished successfully.")


if __name__ == "__main__":
    logger = setup_logger()
    try:
        main()
    except Exception as e:
        logger.exception("An unhandled error occurred: %s", e)
        sys.exit(1)
