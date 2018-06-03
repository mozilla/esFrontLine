import os

from setuptools import setup, find_packages


root = os.path.abspath(os.path.dirname(__file__))
path = lambda *p: os.path.join(root, *p)
assert os.path.exists('README.md'), 'Missing README.md'
long_desc = open(path('README.md')).read()

setup(
    name='esFrontLine',
    version="2.11.18154",
    description='Limit restful requests to backend ElasticSearch cluster:  Queries only.',
    long_description=long_desc,
    author='Kyle Lahnakoski',
    author_email='kyle@lahnakoski.com',
    url='https://github.com/klahnakoski/esFrontLine',
    license='MPL 2.0',
    packages=find_packages(),
    install_requires=["Flask==0.10.1","elasticsearch==6.2.0","mo-dots>=2.7.18148","mo-future>=2.3.18147","mo-logs","mohawk==0.3.4","requests==2.18.4","responses==0.9.0"],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        "console_scripts":[
            "esFrontLine = esFrontLine.app:main"
        ]
    },
    classifiers=[  # https://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 4 - Beta",
        "Topic :: Internet :: Proxy Servers",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 2.7",
    ]
)
