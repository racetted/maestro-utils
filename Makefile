all:
	$(MAKE) -C ssm ssm

clean: 
	$(MAKE) -C ssm $@

distclean: clean
	find . -name "*~" -exec rm -f {} \;

install: all
	cd ssm ; $(MAKE) $@

uninstall:
	$(MAKE) -C ssm $@