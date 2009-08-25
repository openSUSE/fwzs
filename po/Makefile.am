# gettext/intltool automake ingeration really sucks. I do it myself.
#
XGETTEXT = xgettext --keyword=_ --keyword=N_
MSGFMT = msgfmt

LINGUAS = de
DOMAINS = fwzsapp fwzsd

update-po:
	@for d in $(DOMAINS); do \
		$(MAKE) $$d.pot; \
		for i in $(LINGUAS); do \
			n=$${d}_$$i; \
			test -e $$n.po || continue; \
			echo -n "$${d} $$i "; \
			msgmerge $$n $$d.pot -o $$n.po.new && mv $$n.po.new $$n.po; \
		done; \
	done

install-data-local:
	@for d in $(DOMAINS); do \
		for i in $(LINGUAS); do \
			n=$${d}_$$i; \
			test -e $$n.po || continue; \
			$(MSGFMT) -o $$n.mo $$n.po; \
			set -- install -D -m 644 $$n.mo $(DESTDIR)$(localedir)/$$i/LC_MESSAGES/$$d.mo; \
			echo "$$@"; \
			"$$@"; \
		done; \
	done

dist-hook:
	@for d in $(DOMAINS); do \
		cp -p $(srcdir)/$$d.pot $(distdir)/$$d.pot; \
		for i in $(LINGUAS); do \
			n=$${d}_$$i; \
			cp -p $(srcdir)/$$n.po $(distdir)/$$n.po; \
		done; \
	done

fwzsapp.pot: $(top_srcdir)/fwzsapp.py
	$(XGETTEXT) $? -o $@

fwzsd.pot: $(top_srcdir)/fwzsd.py
	$(XGETTEXT) $? -o $@

.PHONY: update-po
