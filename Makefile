PREFIX := /usr

PROGRAMS_SLAVE := slave/scripts/*

build:
	tests/increase-version-number

install_slave: $(scripts)
	mkdir -p $(DESTDIR)/$(PREFIX)/bin/
	mkdir -p $(DESTDIR)/etc/jenkins/
	for prog in $(PROGRAMS_SLAVE); do \
		install -m 0755 $$prog $(DESTDIR)/$(PREFIX)/bin; \
	done

	install -m 0664 slave/config/debian_glue.example $(DESTDIR)/etc/jenkins/
	mkdir -p $(DESTDIR)/usr/share/jenkins-debian-glue/pbuilder-hookdir/
	install -m 0775 slave/pbuilder-hookdir/* $(DESTDIR)/usr/share/jenkins-debian-glue/pbuilder-hookdir/

install_master: $(scripts)
	echo "Nothing to do!"

install: install_master install_slave

uninstall: $(scripts)
	for prog in $(PROGRAMS); do \
		rm $(DESTDIR)/$(PREFIX)/bin/$${prog#scripts} ; \
	done
	rm -rf $(DESTDIR)/usr/share/jenkins-debian-glue/examples
	rmdir --ignore-fail-on-non-empty $(DESTDIR)/usr/share/jenkins-debian-glue

deploy:
	fab all

clean:
	rm -f fabfile.pyc
	# avoid recursion via debian/rules clean, so manually rm:
	rm -f debian/files debian/jenkins-debian-glue.debhelper.log
	rm -f debian/jenkins-debian-glue.substvars
	rm -rf debian/jenkins-debian-glue/

.PHONY: build install install_master install_client
