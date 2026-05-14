#!/bin/bash
# Build copa RPM for Fedora 43 and 44

set -e

PACKAGE="copa"
VERSION="0.1.0"
SPEC_FILE="rpm/copa.spec"

echo "Building ${PACKAGE} ${VERSION} RPM packages..."

# Create build directories
mkdir -p build/SRPMS
mkdir -p build/RPMS

# Build source RPM
echo "Building source RPM..."
rpmbuild -bs ${SPEC_FILE} \
    --define "_topdir $(pwd)/build" \
    --define "_sourcedir $(pwd)"

# Build for Fedora 43
echo "Building for Fedora 43..."
rpmbuild -bb ${SPEC_FILE} \
    --define "_topdir $(pwd)/build" \
    --define "_sourcedir $(pwd)" \
    --define "fedora 43" \
    --target noarch

# Build for Fedora 44
echo "Building for Fedora 44..."
rpmbuild -bb ${SPEC_FILE} \
    --define "_topdir $(pwd)/build" \
    --define "_sourcedir $(pwd)" \
    --define "fedora 44" \
    --target noarch

echo "Build complete!"
echo ""
echo "RPM packages:"
find build/RPMS -name "*.rpm" -type f
echo ""
echo "Source RPM:"
find build/SRPMS -name "*.src.rpm" -type f
