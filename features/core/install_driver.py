import os
import re
import platform
import requests
import pyderman as driver_installer
from pyderman.util import github
from pathlib import Path

CHROMEDRIVER_LATEST_RELEASE = 'https://chromedriver.storage.googleapis.com/LATEST_RELEASE'

paths = dict(Darwin=Path(os.environ.get('VIRTUAL_ENV', Path.cwd()), 'bin'), Windows=Path(Path.cwd(), 'Scripts'))
file_directory = paths.get(platform.system())

is_win_platform = platform.system().lower().startswith('win')


def get_geckodriver_options():
    return dict(
        browser=driver_installer.firefox,
        filename='geckodriver.exe' if is_win_platform else 'geckodriver'
    )


def get_chromedriver_options():
    return dict(
        browser=driver_installer.chrome,
        filename='chromedriver.exe' if is_win_platform else 'chromedriver'
    )


def get_chrome_version(chrome_version_string: str):
    chrome_version = re.search(r'\d+\.\d+\.\d+', chrome_version_string)
    return chrome_version.group(0) if chrome_version else None


def get_chromedriver_version(chrome_version=None):
    version = f'_{chrome_version}' if chrome_version else ''
    r = requests.get(f'{CHROMEDRIVER_LATEST_RELEASE}{version}')
    return r.text


def install(driver_options: dict) -> str:
    driver_path = driver_installer.install(
        **driver_options,
        file_directory=file_directory,
        verbose=True,
        chmod=True,
        overwrite=True
    )
    return driver_path


def install_chromedriver(chromedriver_version_string=None):
    options = get_chromedriver_options()
    if chromedriver_version_string is not None:
        version = get_chromedriver_version(chrome_version=get_chrome_version(chromedriver_version_string))
        options['version'] = version

    return install(options)


def install_geckodriver():
    def patched_ff_url_mac_intel(version='latest', _os=None, _os_bit=None):
        urls = github.find_links('mozilla', 'geckodriver', version)
        for u in urls:
            target = 'macos.'
            if target in u:
                ver = re.search(r'v(\d{1,2}\.\d{1,2}\.\d{1,2})', u).group(1)
                return 'geckodriver', u, ver

    if platform.system() == 'Darwin' and platform.machine() == 'x86_64':
        driver_installer.firefox.get_url = patched_ff_url_mac_intel
    return install(get_geckodriver_options())


if __name__ == '__main__':
    install(get_chromedriver_options())
