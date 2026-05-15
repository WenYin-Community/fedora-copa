.PHONY: build clean test lint

PACKAGE = copa
VERSION = $(shell grep '^Version:' rpm/copa.spec | awk '{print $$2}')
SPEC_FILE = rpm/copa.spec

# Build targets
build: build-fedora43 build-fedora44

build-fedora43:
	@echo "Building for Fedora 43..."
	@mkdir -p build/RPMS build/SRPMS
	@rpmbuild -bb $(SPEC_FILE) \
		--define "_topdir $(CURDIR)/build" \
		--define "_sourcedir $(CURDIR)" \
		--target noarch
	@echo "Fedora 43 build complete!"

build-fedora44:
	@echo "Building for Fedora 44..."
	@mkdir -p build/RPMS build/SRPMS
	@rpmbuild -bb $(SPEC_FILE) \
		--define "_topdir $(CURDIR)/build" \
		--define "_sourcedir $(CURDIR)" \
		--target noarch
	@echo "Fedora 44 build complete!"

build-srpm:
	@echo "Building source RPM..."
	@mkdir -p build/SRPMS
	@rpmbuild -bs $(SPEC_FILE) \
		--define "_topdir $(CURDIR)/build" \
		--define "_sourcedir $(CURDIR)"
	@echo "Source RPM build complete!"

# Development targets
install-dev:
	pip install --user -e ".[dev]"

test:
	python3 -m pytest tests/ -v

lint:
	ruff check .
	mypy copa/

# Clean
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +

# Show build artifacts
show:
	@echo "Build artifacts:"
	@find build -name "*.rpm" -type f 2>/dev/null || echo "No RPMs built yet"
