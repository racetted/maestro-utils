# this file contains common config that is sourced by all makefiles
VERSION=1.5.0
ARCH=all
SWDEST=$(shell pwd)/..

# platform specific definition
SSMPACKAGE=maestro-utils_${VERSION}_$(ARCH)
