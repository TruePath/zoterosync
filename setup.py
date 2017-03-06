import os
from setuptools import setup, find_packages

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(name='zoterosync',
      version='0.2',
      description='Persistant Syncing with Zotero',
      author='Peter Gerdes',
      author_email='gerdes@invariant.org',
      license='MIT',
      packages=find_packages(),
      long_description=read('README'),
      classifiers=[
        "Development Status :: 3 - Alpha",
        'Programming Language :: Python :: 3.5',
      ],
      install_requires=[
        'Click', 'pyzotero', 'python-dateutil', 'nameparser'
      ],
      setup_requires=['pytest-runner'],
      tests_require=['pytest'],
      zip_safe=False,
      entry_points='''
        [console_scripts]
        zotero=zoterosync.script:cli
    ''')
