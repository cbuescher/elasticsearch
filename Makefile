test:
	python3 setup.py test

install: configure
	@ ./install.sh

configure:
	@ ./night_rally/fixtures/ansible/configure.sh

.PHONY: test install configure
