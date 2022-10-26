from setuptools import setup, find_packages
import codecs
import os

ROOT_PATH = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(ROOT_PATH, 'README.md'), encoding='utf-8') as fh:
    long_description = '\n' + fh.read()

VERSION = '0.0.1'
DESCRIPTION = 'Collection of easy to use API to common services'

setup(
    name='python_apis',
    version=VERSION,
    authors=[
        { 'name': 'Björn Gunnarsson', 'email': 'bosos3@hotmail.com' },
    ],
    description=DESCRIPTION,
    long_description_content_type='text/markdown',
    long_description=long_description,
    keywords='AD, Active Directory, SQL server, mssql',
    packages=find_packages(where="src"),
    python_requires='>=3.7',
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows',
    ],
    install_requires=[],
    extras_require={
        'dev': ['pytest'],
    },
    project_urls={
        "Bug Reports": "https://github.com/Kopavogur/Python-APIs/issues",
        "Source": 'https://github.com/Kopavogur/Python-APIs',
    },
)