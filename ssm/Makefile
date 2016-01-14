# ATTENTION!
# YOU NEED TO USE THE GMAKE IN /users/dor/afsi/sul/ovbin/gmake for this
# Makefile to work, other versions installed are currently too old!
#
# common section definition
include ../config/config.mk

ssm: profile.sh
	echo "Creating SSM package $(SSMPACKAGE)..."
	if [ ! -d $(SSMPACKAGE) ]; then \
	   mkdir $(SSMPACKAGE); \
	   mkdir $(SSMPACKAGE)/ssm; \
	fi;
	cp -r $(SWDEST)/bin $(SSMPACKAGE);
	cp -r $(SWDEST)/lib $(SSMPACKAGE);
	cp ../Makefile $(SSMPACKAGE);
	cp ../LICENSE.txt $(SSMPACKAGE);
	cp Makefile $(SSMPACKAGE)/ssm;
	mkdir -p $(SSMPACKAGE)/.ssm.d;
	cp -r post-install profile.sh $(SSMPACKAGE)/.ssm.d;
	echo "Package: maestro-utils" > $(SSMPACKAGE)/.ssm.d/control; \
	echo "Version: ${VERSION}" >> $(SSMPACKAGE)/.ssm.d/control; \
	echo "Platform: all" >> $(SSMPACKAGE)/.ssm.d/control; \
	echo "Maintainer: $(shell whoami)" >> $(SSMPACKAGE)/.ssm.d/control; \
	echo "BuildInfo:" >> $(SSMPACKAGE)/.ssm.d/control; \
	echo "Description: Maestro Utilities" >> $(SSMPACKAGE)/.ssm.d/control; \
	tar cvf - $(SSMPACKAGE) | gzip -> $(SSMPACKAGE).ssm

profile.sh: Makefile ../config/config.mk
	touch profile ;\
	echo "export SEQ_UTILS_VERSION=${VERSION}" >$@ ;\
	cat profile >>$@

clean:
	rm -rf $(SSMPACKAGE).ssm $(SSMPACKAGE) profile.sh
