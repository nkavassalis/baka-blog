.PHONY: all clean default

default:
	python3 make.py

clean:
	rm -f .file_hashes.json .slug_uuid_mapping.json

all: clean default
