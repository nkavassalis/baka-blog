.PHONY: all clean default setup

default:
	python3 make.py

setup:
	python3 make.py setup

clean:
	rm -f .file_hashes.json .slug_uuid_mapping.json

all: clean default
