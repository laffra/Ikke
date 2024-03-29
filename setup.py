import atexit
from distutils import cmd
from setuptools import setup, find_packages
from setuptools.command.install import install
from subprocess import check_call

REQUIRED_PACKAGES = [
    'rumps',
    'jinja2',
    'dateparser',
    'psutil',
    'py2app',
    'google-api-python-client',
    'google-auth-httplib2',
    'google-auth-oauthlib',
    'PyDriller',
    'pyinstaller',
    'python-dateutil',
    'elasticsearch',
]


class CustomInstall(install):
    def run(self):
        def _post_install():
            print("### Installing latest ElasticSearch using brew")
            check_call(['brew', 'tap', 'elastic/tap'])
            check_call(['brew', 'install', 'elastic/tap/elasticsearch-full'])
            check_call(['brew', 'install', 'elastic/tap/kibana-full'])
            for package in REQUIRED_PACKAGES:
                check_call(['python3', '-m', 'pip', 'install', package])

        atexit.register(_post_install)
        install.run(self)


setup(
    name = 'install',
    version = '0.1.0',
    packages = find_packages(),
    install_requires = REQUIRED_PACKAGES,
    cmdclass = {
        'install': CustomInstall,
    },
)