.PHONY: all clean default setup prune

default:
	python3 make.py

setup:
	python3 make.py setup

prune:
	python3 make.py prune

clean:
	rm -f .file_hashes.json .slug_uuid_mapping.json

all: clean default
