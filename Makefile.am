sbin_SCRIPTS = fwzsd
bin_SCRIPTS = fwzsapp

icondir = $(pkgdatadir)/icons
icon_DATA = firewall.png

dbusdatadir = @dbusdatadir@
dbussystemservicedir = $(dbusdatadir)/system-services
dbussystemservice_DATA = org.opensuse.zoneswitcher.service

do_subst = sed -e 's,[@]sbindir[@],$(sbindir),'
do_subst_py = sed -e '/+++automake/{s@ICONDIR = .*@ICONDIR = "$(icondir)"@}'

fwzsd: fwzsd.py Makefile
	@echo "creating $@"
	@$(do_subst_py) $(srcdir)/$< > $@
	@chmod +x $@

fwzsapp: fwzsapp.py Makefile
	@echo "creating $@"
	@$(do_subst_py) $(srcdir)/$< > $@
	@chmod +x $@

org.opensuse.zoneswitcher.service: org.opensuse.zoneswitcher.service.in Makefile
	@echo "creating $@"
	@$(do_subst) $(srcdir)/$< > $@

CLEANFILES = $(sbin_SCRIPTS)
EXTRA_DIST = fwzsd.py fwzsapp.py org.opensuse.zoneswitcher.service.in
