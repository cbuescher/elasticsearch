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
    "elasticsearch==6.2.0",
    "tabulate==0.8.1",
    "certifi"
]

tests_require = [
    "pytest==3.4.2"
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
      package_data={"": ["*.json", "*.yml", "*.cfg", "*.j2"]},
      install_requires=install_requires,
      test_suite="tests",
      tests_require=tests_require,
      setup_requires=[
          "pytest-runner==2.10.1",
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
          "Programming Language :: Python :: 3.4",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6"
      ],
      zip_safe=False)
