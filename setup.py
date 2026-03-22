# Automatically created by: shub deploy

from setuptools import setup, find_packages

setup(
    name         = 'radarlicencias-crawlers',
    version      = '1.0',
    packages     = find_packages(),
    package_data = {'radarlicencias': ['data/*.txt']},
    include_package_data = True,
    entry_points = {'scrapy': ['settings = radarlicencias.settings']},
)
