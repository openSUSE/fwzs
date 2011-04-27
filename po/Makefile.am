# gettext/intltool automake integration really sucks. I do it myself.
#
XGETTEXT = xgettext --keyword=_ --keyword=N_
MSGFMT = msgfmt

LINGUAS = de
DOMAINS = fwzsapp fwzsd

mos = $(foreach lang,$(LINGUAS),$(addsuffix _$(lang).mo,$(DOMAINS)))

all-local: $(mos)

%.mo: %.po
	$(MSGFMT) -o $@ $<

update-po:
	@for d in $(DOMAINS); do \
		$(MAKE) $$d.pot; \
		for i in $(LINGUAS); do \
			n=$${d}_$$i; \
			test -e $$n.po || continue; \
			echo -n "$${d} $$i "; \
			if ! msgcmp $$n.po $$d.pot 2>/dev/null; then \
			    msgmerge $$n $$d.pot -o $$n.po.new && mv $$n.po.new $$n.po; \
			else \
			    echo unchanged; \
			fi; \
		done; \
	done

install-data-local: $(mos)
	@for d in $(DOMAINS); do \
		for i in $(LINGUAS); do \
			n=$${d}_$$i; \
			test -e $$n.po || continue; \
			set -- install -D -m 644 $$n.mo $(DESTDIR)$(localedir)/$$i/LC_MESSAGES/$$d.mo; \
			echo "$$@"; \
			"$$@"; rm -f $$n.mo; \
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

clean-local:
	rm -f $(mos)

fwzsapp.pot: $(top_srcdir)/fwzsapp.py
	$(XGETTEXT) $? -o $@

fwzsd.pot: $(top_srcdir)/fwzsd.py
	$(XGETTEXT) $? -o $@

.PHONY: update-po
