define([dbusdatadirdefault],[${datadir}/dbus-1])dnl
dnl
AC_INIT([fwzs],[0.4],[ludwig.nussel@suse.de])
AC_CONFIG_SRCDIR([fwzsd.py])

AC_PREREQ(2.53)
AC_CANONICAL_HOST
AM_INIT_AUTOMAKE([1.6 foreign dist-bzip2 no-dist-gzip])

AC_ARG_WITH([dbusdatadir],
	[AS_HELP_STRING([--with-dbusdatadir],
			[path for dbus data files (default="]dbusdatadirdefault[")])],
	[],
	[with_dbusdatadir="dbusdatadirdefault"])
dbusdatadir="$with_dbusdatadir"
AC_SUBST(dbusdatadir)

AC_CONFIG_FILES([
	Makefile
	po/Makefile
])
AC_OUTPUT
