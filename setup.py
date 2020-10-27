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

# tuples of (major, minor) of supported Python versions ordered from lowest to highest
supported_python_versions = [(3, 8)]

install_requires = [
    # required for night-rally fixtures and deploying ini files
    "ansible==2.9.6",
    # License: Apache 2.0
    # transitive dependency urllib3: MIT
    "elasticsearch==7.9.1",
    # required by hashi_vault ansible plugin
    "hvac==0.9.1",
    # License: MIT
    "jsonschema==3.1.1",
    # License: MIT
    "tabulate==0.8.7",
    # always use the latest version, these are certificate files...
    # License: MPL 2.0
    "certifi"
]

tests_require = [
    "pytest==5.4.0",
    "pytest-asyncio==0.14.0"
]

python_version_classifiers = ["Programming Language :: Python :: {}.{}".format(major, minor)
                              for major, minor in supported_python_versions]

first_supported_version = "{}.{}".format(supported_python_versions[0][0], supported_python_versions[0][1])
# next minor after the latest supported version
first_unsupported_version = "{}.{}".format(supported_python_versions[-1][0], supported_python_versions[-1][1] + 1)

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
      # https://packaging.python.org/guides/distributing-packages-using-setuptools/#python-requires
      python_requires=">={},<{}".format(first_supported_version, first_unsupported_version),

      package_data={"": ["*.json", "*.yml", "*.cfg", "*.j2"]},
      install_requires=install_requires,
      test_suite="tests",
      tests_require=tests_require,
      setup_requires=[
          "pytest-runner==5.1",
      ],
      entry_points={
          "console_scripts": [
              # This should not clash with the shell script (which is symlinked as "night_rally" in our CI environment)!
              "es-night-rally=night_rally.night_rally:main",
              "night-rally-admin=night_rally.admin:main"
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
      ] + python_version_classifiers,
      zip_safe=False)
