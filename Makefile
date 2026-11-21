PREFIX ?= /usr/local
DESTDIR ?=
CGD ?= cgd
VERSION := 0.1.0
DIST_NAME := dcc-$(VERSION)-linux-x86_64

.PHONY: all build test verify format check-format install uninstall dist clean

all: build

build:
	CGD="$(CGD)" ./bootstrap/build.sh

test: build
	python3 tests/run_tests.py

verify: build
	./bootstrap/verify.sh

format:
	@for f in $$(find src -name '*.delegua' | sort); do \
		"$(CGD)" --formatar "$$f" || exit 1; \
	done

check-format:
	@for f in $$(find src -name '*.delegua' | sort); do \
		"$(CGD)" --verificar-formatacao "$$f" || exit 1; \
	done

install: build
	install -d "$(DESTDIR)$(PREFIX)/bin"
	install -m 0755 build/dcc "$(DESTDIR)$(PREFIX)/bin/dcc"

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)/bin/dcc"

dist: build
	rm -rf "dist/$(DIST_NAME)"
	mkdir -p "dist/$(DIST_NAME)/bin" "dist/$(DIST_NAME)/docs"
	install -m 0755 build/dcc "dist/$(DIST_NAME)/bin/dcc"
	cp README.md LICENSE CHANGELOG.md "dist/$(DIST_NAME)/"
	cp docs/*.md "dist/$(DIST_NAME)/docs/"
	ldd build/dcc > "dist/$(DIST_NAME)/DEPENDENCIES.txt"
	tar -C dist -czf "dist/$(DIST_NAME).tar.gz" "$(DIST_NAME)"
	@echo "Pacote gerado em dist/$(DIST_NAME).tar.gz"

clean:
	rm -rf build dist a.out a.s *.o
