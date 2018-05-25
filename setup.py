import os

from setuptools import setup


root = os.path.abspath(os.path.dirname(__file__))
path = lambda *p: os.path.join(root, *p)
assert os.path.exists('README.txt'), 'Missing README.txt'
long_desc = open(path('README.txt')).read()

setup(
    name='esFrontLine',
    version="1.1.14230",
    description='Limit restful requests to backend ElasticSearch cluster:  Queries only.',
    long_description=long_desc,
    author='Kyle Lahnakoski',
    author_email='kyle@lahnakoski.com',
    url='https://github.com/klahnakoski/esFrontLine',
    license='MPL 2.0',
    packages=['esFrontLine'],
    install_requires=[
        'Flask==0.10.1',
        'requests==2.3.0',
        'mohawk==0.3.4',
    ],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        "console_scripts":[
            "esFrontLine = esFrontLine.app:main"
        ]
    },
    classifiers=[  #https://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Internet :: Proxy Servers",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
    ]
)
