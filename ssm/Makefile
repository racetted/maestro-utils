# ATTENTION!
# YOU NEED TO USE THE GMAKE IN /users/dor/afsi/sul/ovbin/gmake for this
# Makefile to work, other versions installed are currently too old!
#
# common section definition
include config.mk

ssm: 
	echo "Creating SSM package $(SSMPACKAGE)..."
	if [ ! -d $(SSMPACKAGE) ]; then \
	   mkdir $(SSMPACKAGE); \
	fi;
	cp -r $(SWDEST)/bin $(SSMPACKAGE); 
	mkdir -p $(SSMPACKAGE)/.ssm.d;
	cp -r pre-publish $(SSMPACKAGE)/.ssm.d;
	cp -r post-install $(SSMPACKAGE)/.ssm.d;
	ssmprep --basePath $(PWD)/$(SSMPACKAGE) -p $(SSMPACKAGE) --editorPath /bin/echo;
	echo "Package: maestro-utils" > $(SSMPACKAGE)/.ssm.d/control; \
	echo "Version: ${VERSION}" >> $(SSMPACKAGE)/.ssm.d/control; \
	echo "Platform: all" >> $(SSMPACKAGE)/.ssm.d/control; \
	echo "Maintainer: $(shell whoami)" >> $(SSMPACKAGE)/.ssm.d/control; \
	echo "BuildInfo:" >> $(SSMPACKAGE)/.ssm.d/control; \
	echo "Description: Maestro Utilities" >> $(SSMPACKAGE)/.ssm.d/control; \
	tar cvf - $(SSMPACKAGE) | gzip -> $(SSMPACKAGE).ssm

clean:
	rm -r $(SSMPACKAGE).ssm $(SSMPACKAGE)