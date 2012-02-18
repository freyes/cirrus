import os
from setuptools import setup, find_packages
from cirrus import __version__

dependencies = ["boto", "PyYAML"]


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="cirrus",
    version=__version__,
    author="Felipe Reyes",
    author_email="freyes@tty.cl",
    description=("Viewer for clouds with EC2 compatible API"),
    license="GPLv3",
    keywords="ec2 cloud aws openstack",
    packages=find_packages(),
    include_package_data=True,
    long_description=read('README'),
    install_requires=dependencies,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
    ],
    entry_points={
        'console_scripts': [
            'cirrus = cirrus.app:main',
        ]},
        )
