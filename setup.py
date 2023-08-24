from os.path import join, dirname

try:
    from setuptools import setup, find_packages
except ImportError:
    print("*** Could not find setuptools. Did you install pip3? *** \n\n")
    raise


def str_from_file(name):
    with open(join(dirname(__file__), name)) as f:
        return f.read().strip()


VERSION = "1.0.0.dev0"
__version__ = VERSION
__versionstr__ = VERSION

long_description = str_from_file("README.md")

install_requires = [
    # required for night-rally fixtures and deploying ini files
    "ansible==2.10.7",
    # License: Apache 2.0
    # transitive dependency urllib3: MIT
    "elasticsearch==8.6.1",
    "elastic-transport==8.4.0",
    # required by hashi_vault ansible plugin
    "hvac==0.9.1",
    # License: MIT
    "jsonschema==3.1.1",
    # License: MIT
    "tabulate==0.8.9",
    # always use the latest version, these are certificate files...
    # License: MPL 2.0
    "certifi"
]

tests_require = [
    "pytest==6.2.5",
    "pytest-asyncio==0.16.0"
]

setup(name="night_rally",
      version=__versionstr__,
      description="Nightly Benchmark Scripts for Elasticsearch Benchmarks based on Rally",
      long_description=long_description,
      url="https://github.com/elastic/night-rally",
      packages=find_packages(
          where=".",
          exclude=("tests*", "external*")
      ),
      include_package_data=True,
      python_requires=">=3.8",
      package_data={"": ["*.json", "*.yml", "*.cfg", "*.j2"]},
      install_requires=install_requires,
      extras_require={
          "develop": tests_require,
      },
      entry_points={
          "console_scripts": [
              # This should not clash with the shell script (which is symlinked as "night_rally" in our CI environment)!
              "es-night-rally=night_rally.night_rally:main",
          ],
      },
      classifiers=[
          "Topic :: System :: Benchmark",
          "Development Status :: 5 - Production/Stable",
          "Intended Audience :: Developers",
          "Operating System :: MacOS :: MacOS X",
          "Operating System :: POSIX",
          "Programming Language :: Python",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
      ],
      zip_safe=False)
