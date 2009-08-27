sbin_SCRIPTS = fwzsd
bin_SCRIPTS = fwzsapp

icondir = $(pkgdatadir)/icons
icon_DATA = firewall.png

desktopdatadir = $(datadir)/applications
desktopdata_DATA = fwzsapp.desktop

dbusdatadir = @dbusdatadir@
dbussystemservicedir = $(dbusdatadir)/system-services
dbussystemservice_DATA = org.opensuse.zoneswitcher.service

dbussystemconfigdir = $(sysconfdir)/dbus-1/system.d
dbussystemconfig_DATA = org.opensuse.zoneswitcher.conf

policydir = $(datadir)/PolicyKit/policy
policy_DATA = org.opensuse.zoneswitcher.policy

do_subst = sed -e 's,[@]sbindir[@],$(sbindir),' \
	   -e 's,[@]bindir[@],$(bindir),' \
	   -e 's,[@]icondir[@],$(icondir),'
do_subst_py = sed -e '/+++automake/{s@ICONDIR *= .*@ICONDIR = "$(icondir)"@;s@BINDIR *= .*@BINDIR = "$(bindir)"@}'

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

fwzsapp.desktop: fwzsapp.desktop.in Makefile
	@echo "creating $@"
	@$(do_subst) $(srcdir)/$< > $@

CLEANFILES = $(sbin_SCRIPTS) $(bin_SCRIPTS) $(dbussystemservice_DATA) $(desktopdata_DATA)
EXTRA_DIST = fwzsd.py fwzsapp.py \
	     org.opensuse.zoneswitcher.service.in \
	     fwzsapp.desktop.in \
	     firewall.png \
	     org.opensuse.zoneswitcher.policy \
	     org.opensuse.zoneswitcher.conf

SUBDIRS = po
