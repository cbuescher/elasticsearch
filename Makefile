test:
	python3 setup.py test

setup: install configure

install:
	@ ./install.sh

configure:
	@ ./night_rally/fixtures/ansible/configure.sh

.PHONY: setup test install
