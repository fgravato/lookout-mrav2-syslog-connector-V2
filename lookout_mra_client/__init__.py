from importlib_metadata import version, PackageNotFoundError


def __get_version():
    """
    importlib.metadata works when mrav2_syslog_connector is installed as a package, but not
    when running tests.
    """
    try:
        return version("mrav2_syslog_connector")
    except PackageNotFoundError:
        return "Unknown"


__version__ = __get_version()
__prj_name__ = f"mrav2-syslog-connector/{__version__}"
