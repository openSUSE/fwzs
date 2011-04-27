#!/usr/bin/python
#
# fwszapp - fwzs tray applet
# Copyright (C) 2009 SUSE LINUX Products GmbH
#
# Author:     Ludwig Nussel
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# version 2 as published by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

ICONDIR = '.' # +++automake+++
BINDIR  = '.' # +++automake+++

import glib
import gtk
import sys
from traceback import print_exc
import os
import ConfigParser

import dbus
import dbus.mainloop.glib

import gettext
import locale

gettext.install('fwzsapp')

icon_green = ICONDIR + '/firewall.png'
icon_yellow = ICONDIR + '/firewall_y.png'
icon_red = ICONDIR + '/firewall_x.png'
icon_grey = ICONDIR + '/firewall_g.png'

xdg_configdir = os.path.expanduser(os.getenv('XDG_CONFIG_HOME', '~/.config'))

txt_no_zones_found = _("No zones found.\nFirewall not running or fwzs not supported?")

class DesktopAutoStart:
    def __init__(self):
	self.file = xdg_configdir + '/autostart/fwzs.desktop'

    def is_enabled(self):
	if os.access(self.file, os.F_OK):
	    return True
	return False

    def enable(self, enable=None):
	if enable == None or enable:
	    script = sys.argv[0]
	    if script and (script[0:1] != '/' or not os.access(script, os.X_OK)):
		print "enable autostart not possible"
		return False

	    try:
		dir = os.path.dirname(self.file)
		if not os.access(dir, os.F_OK):
		    os.makedirs(dir)
		out = open(self.file, "w")
		out.write("""[Desktop Entry]
Name=Firewall Zone Switcher
Comment=System Tray applet that allows to switch firewall zones
Terminal=false
Type=Application
StartupNotify=false
""")
		out.write("Exec="+script+" --tray --delay=5\n")
		out.close()
		return True

	    except Exception, e:
		print e
	    return False
	else:
	    return self.disable()

    def disable(self):
	try:
	    if os.access(self.file, os.F_OK):
		os.remove(self.file)
	    return True
	except Exception, e:
	    print e
	return False

class Config:

    def __init__(self):
	self.file = xdg_configdir + '/fwzs/config'
	self.config = ConfigParser.RawConfigParser()
	self.config.read(self.file)

    def getbool(self, section, option, default=None):
	if self.config.has_option(section, option):
	    v = self.config.get(section, option)
	    if v == 'True':
		return True
	    return False
	return default

    def set(self, section, option, value):
	if not self.config.has_section(section):
	    self.config.add_section(section)
	self.config.set(section, option, str(value))

    def save(self):
	try:
	    dir = os.path.dirname(self.file)
	    if not os.access(dir, os.F_OK):
		os.makedirs(dir)
	    out = open(self.file, "wb")
	    self.config.write(out)
	except Exception, e:
	    print e


class SettingsDialog:

    def __init__(self, parent, app):
	self.app = app
	dialog = gtk.Dialog(_("Settings"), parent, gtk.DIALOG_MODAL,
		(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
	dialog.set_icon_from_file(icon_green)
	v = gtk.VBox()
	v.set_border_width(6)

	self.trayiconcb = gtk.CheckButton(_("System Tray Icon"))
	if app.config.getbool('general', 'systray', False):
	    self.trayiconcb.set_active(True)
	v.pack_start(self.trayiconcb)

	self.autostartcb = gtk.CheckButton(_("Start on Log-in"))
	if DesktopAutoStart().is_enabled():
	    self.autostartcb.set_active(True)
	v.pack_start(self.autostartcb)

	v.show_all()
	dialog.get_child().pack_start(v)

	dialog.show()
	dialog.connect('response', lambda dialog, id: self.response(dialog, id))

    def response(self, dialog, id):
	dialog.destroy()

	if id != gtk.RESPONSE_ACCEPT:
	    return

	v = self.trayiconcb.get_active()
	self.app.config.set('general', 'systray', v)
	if v:
	    self.app.icon.show()
	else:
	    self.app.icon.hide()

	v = self.autostartcb.get_active()
	DesktopAutoStart().enable(v)

	self.app.config.save()

#    def __del__(self):
#	print "destruct"

class ChangeZoneDialog:

    def __init__(self, parent, app, iface):
	self.app = app
	self.selection = None
	zones = app.iface.Zones()
	ifaces = app.iface.Interfaces()
	if not zones or not ifaces:
	    app.error_dialog(_("Can't get list of interfaces or zones"))
	    return

	dialog = gtk.Dialog(_("Choose Zone for %s") % iface, parent, gtk.DIALOG_MODAL,
		(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
	dialog.set_icon_from_file(icon_green)
	vbox = dialog.get_child()
	v = gtk.VBox()
	v.set_border_width(6)
	group = None
	for z in zones:
	    txt = zones[z]
	    if not txt:
		txt = z
	    rb = gtk.RadioButton(group, txt)
	    group = rb
	    if z == ifaces[iface]:
		rb.set_active(True)
		self.selection = (iface, z)
	    rb.connect('toggled', lambda *args: self._zone_selected(*args), iface, z)
	    v.pack_start(rb, False, False)
	    rb.show()

	v.show_all()
	vbox.pack_start(v, True, True)
	dialog.show()
	dialog.connect('response', lambda dialog, id: self.change_zone_dialog_response(dialog, id))

    def _zone_selected(self, item, iface, zone):
	if not item.get_active():
	    return

	self.selection = (iface, zone)

    def change_zone_dialog_response(self, dialog, id):
	dialog.destroy()
	if id != gtk.RESPONSE_ACCEPT:
	    return

	if not self.selection:
	    print "error: no active item"

	self.app.set_zone(self.selection[0], self.selection[1])

class StatusIcon:

    def __init__(self, app):
	self.icon = None
	self.app = app
	self.iconfile = icon_grey

    def show(self):
	if not self.icon:
	    self.icon = gtk.status_icon_new_from_file(self.iconfile)
	    self.icon.connect('popup-menu', lambda i, eb, et: self.show_menu(i, eb, et))
	    self.icon.connect('activate', lambda *args: self.app.toggle_overview_dialog())
	else:
	    self.icon.set_visible(True)

    def isshown(self):
	if self.icon and self.icon.get_visible():
	    return True
	return False

    def hide(self):
	# no idea how to destroy it, so hide it
	if self.icon:
	    self.icon.set_visible(False)

    def _set_icon(self, file):
	
	if self.iconfile != file:
	    self.iconfile = file
	    if self.app.overview_dialog:
		self.app.overview_dialog.set_contents()

	    if self.icon:
		self.icon.set_from_file(self.iconfile)

    def grey(self):
	self._set_icon(icon_grey)

    def green(self):
	self._set_icon(icon_green)

    def red(self):
	self._set_icon(icon_red)

    def yellow(self):
	self._set_icon(icon_yellow)

    def _menu_error(self, menu, txt):
	item = gtk.MenuItem(txt)
	item.set_sensitive(False)
	item.show()
	menu.append(item)

    def _change_zone(self, item, iface, zone):
	if not item.get_active():
	    return

	self.app.set_zone(iface, zone)

    def show_menu(self, icon, event_button, event_time):

	menu = gtk.Menu()
	self.app.check_status()

	if(not self.app.getzsiface()):
	    item = gtk.MenuItem(_("zoneswitcher service not running"))
	    item.set_sensitive(False)
	    item.show()
	    menu.append(item)
	
	else:
	    zones = self.app.iface.Zones()

	    if zones:
		ifaces = self.app.iface.Interfaces()

		if ifaces:
		    item = gtk.MenuItem(_("Firewall interfaces"))
		    item.set_sensitive(False)
		    item.show()
		    menu.append(item)

		    for i in ifaces:
			item = gtk.MenuItem(i)
			item.show()
			menu.append(item)
			group = None
			submenu = gtk.Menu()
			for z in zones:
			    txt = zones[z]
			    if not txt:
				txt = z
			    zitem = gtk.RadioMenuItem(group, txt)
			    group = zitem
			    if z == ifaces[i]:
				zitem.set_active(True)
			    zitem.connect('toggled', lambda *args: self._change_zone(*args), i, z)
			    zitem.show()
			    submenu.append(zitem)
			item.set_submenu(submenu)

		else:
		    item = gtk.MenuItem(_("No interfaces found."))
		    item.set_sensitive(False)
		    item.show()
		    menu.append(item)

	    else:
		self._menu_error(menu, txt_no_zones_found)

	    item = gtk.MenuItem(_("Run Firewall"))
	    item.connect('activate', lambda *args: self.app.run_firewall())
	    item.show()
	    menu.append(item)

	item = gtk.SeparatorMenuItem()
	item.show()
	menu.append(item)

	item = gtk.MenuItem(_("Quit"))
	item.connect('activate', lambda *args: gtk.main_quit())
	item.show()
	menu.append(item)

	menu.popup(None, None,
	    gtk.status_icon_position_menu, event_button,
	    event_time, icon)

class OverviewDialog:

    def __init__(self, app):

	self.app = app
	closebutton = gtk.STOCK_QUIT
	self.content = None
	self.ifaces = None
	self.zones = None
	if app.icon.isshown():
	    closebutton = gtk.STOCK_CLOSE
	dialog = gtk.Dialog(_("Firewall Zone Switcher"), None, 0, ( closebutton, gtk.RESPONSE_CANCEL ))
	dialog.set_default_size(400, 250)
	dialog.set_icon_from_file(icon_green)

	dialog.connect('response', lambda dialog, id: self.response(id))
	self.dialog = dialog

	self.set_contents()

	dialog.show()

    def create_button_area(self, dialog):

	vbox = gtk.VBox()
	vbox.set_border_width(3)

	if(not self.app.bus):
	    w = gtk.Label("DBus not running")
	    vbox.pack_start(w)

	elif(not self.app.getzsiface()):
	    w = gtk.Label(_("zoneswitcher service not running"))
	    vbox.pack_start(w)
	else:
	    try:
		self.zones = self.app.iface.Zones()
	    except Exception, e:
		print e
		pass

	    if not self.zones:
		vbox.set_border_width(6)
		vbox.set_spacing(6)
		w = gtk.Label(txt_no_zones_found)
		vbox.pack_start(w, False, False)
		w = gtk.Button(_("Run Firewall"))
		w.connect('clicked', lambda *args: self.app.run_firewall())
		vbox.pack_start(w, False, False)
	    else:
		self.ifaces = self.app.iface.Interfaces()

		if self.ifaces:
		    for i in self.ifaces:
			z = self.ifaces[i]
			txt = self.make_label(i, z)
			w = gtk.Button(txt)
			w.connect('clicked', lambda button, i: ChangeZoneDialog(dialog, self.app, i), str(i))
			self.dialog.set_data(i, w)
			vbox.pack_start(w, False, False)

	return vbox

    def make_label(self, i, z):
	if z:
	    if self.zones[z]:
		z = self.zones[z]
	else:
	    z = _("Unknown")
	txt = '%s - %s' % (i, z)
	return txt

    def zone_changed(self, iface, zone):
	if not self.dialog:
	    return

	self.ifaces[iface] = zone
	button = self.dialog.get_data(iface)
	txt = self.make_label(iface, zone)
	if button:
	    button.set_label(txt)

    def set_contents(self):

	dialog = self.dialog

	vbox = gtk.VBox()
	vbox.set_border_width(3)

	h = gtk.HBox()
	i = gtk.image_new_from_file(self.app.icon.iconfile)
	i.set_alignment(1, 0.5)
	l = gtk.Label(_("Firewall Zone Switcher"))
	l.set_alignment(0, 0.5)
	h.pack_start(i, True, True)
	h.pack_start(l, True, True)
	vbox.pack_start(h, False, False)

	frame = gtk.Frame(_("Interfaces"))
	frame.set_border_width(3)
	frame.add(self.create_button_area(dialog))
	vbox.pack_start(frame, True, True, 0)

	b = gtk.Button(_("Settings..."))
	b.connect('clicked', lambda button, *args: SettingsDialog(dialog, self.app))
	h = gtk.HBox()
	h.pack_start(b, False, False, 0)
	vbox.pack_start(h, False, False, 0)

	vbox.show_all()

	if self.content:
	    dialog.get_child().remove(self.content)
	self.content = vbox
	dialog.get_child().pack_start(self.content)

    def response(self, id):
	self.dialog.destroy()
	self.dialog = None
	self.app.overview_dialog = None

	if not self.app.icon.isshown():
	    gtk.main_quit()

    def cancel(self):
	self.dialog.response(gtk.RESPONSE_CANCEL)

class fwzsApp:

    def __init__(self, trayonly=False, delay=0):
	self.bus = self.obj = self.iface = None
	self.config = Config()
	self.icon = StatusIcon(self)
	self.overview_dialog = None

	if delay:
	    glib.timeout_add_seconds(delay, self.startup_timer)
	else:
	    self.check_status()

	if trayonly or self.config.getbool('general', 'systray', False):
	    self.icon.show()

	if not trayonly:
	    self.overview_dialog = OverviewDialog(self)

    def startup_timer(self):
	if not self.bus:
	    self.check_status()
	return False

    def nameowner_changed_handler(self, name, old, new):
	if name != 'org.opensuse.zoneswitcher':
	    return
	
	if(not new and old):
	    self.obj = self.iface = None
	    self.icon.grey()

	elif(not old and new):
	    self.check_status()

    def catchall_handler(self, *args, **kwargs):
	print "args: ", args
	print "kwargs: ", kwargs

    def bus_disconnected(self):
	print "bus disconnected"
	self.icon.grey()

    def check_status(self):
	try: 
	    self.getzsiface()
	    try: 
		if self.iface.Status():
		    self.icon.green()
		else:
		    self.icon.red()
	    except Exception, e:
		print e
		self.icon.grey()
	except:
		self.icon.grey()

    def getzsiface(self):
	if(not self.bus):
	    try:
		self.bus = dbus.SystemBus()

		self.bus.call_on_disconnection(lambda arg: self.bus_disconnected())

		self.bus.set_exit_on_disconnect(False)

#		self.bus.add_signal_receiver(
#			lambda *args: self.catchall_handler(args))

		self.bus.add_signal_receiver(
			lambda name, old, new: self.nameowner_changed_handler(name, old, new),
			dbus_interface='org.freedesktop.DBus',
			signal_name='NameOwnerChanged')

	    except dbus.DBusException, e:
		print "can't connect to bus:", str(e)
		self.bus = self.obj = self.iface = None
		self.icon.grey()
		return None

	if(not (self.obj and self.iface)):
	    try:
		self.obj = self.bus.get_object("org.opensuse.zoneswitcher",
					       "/org/opensuse/zoneswitcher0")

		self.iface = dbus.Interface(self.obj, "org.opensuse.zoneswitcher")

		l = locale.getlocale(locale.LC_MESSAGES)
		if l[0]:
		    self.iface.setLang(l[0])

		#print self.obj.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable")

	    except dbus.DBusException, e:
		self.obj = self.iface = None
		print "can't connect to zoneswitcher:", e
		return None

	return self.iface

    def error_dialog(self, msg, title=_("Firewall Error")):
	d = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, msg)
	d.set_title(title)
	d.run()
	d.destroy()

    def set_zone(self, iface, zone):
	repeat = True
	while repeat:
	    repeat = False
	    try:
		self.iface.setZone(iface, zone)
		self.run_firewall()
		if self.overview_dialog:
		    self.overview_dialog.zone_changed(iface, zone)
	    except dbus.DBusException, e:
		if e.get_dbus_name() == 'org.freedesktop.PolicyKit.NotPrivilegedException':
		    if self.polkitauth(Exception.__str__(e)):
			repeat = True
		else:
		    self.error_dialog(str(e))
	    except Exception, e:
		self.error_dialog(str(e))
		return

    def run_firewall(self):
	ret = False
	repeat = True
	while repeat:
	    repeat = False
	    try:
		ret = self.iface.Run()
	    except dbus.DBusException, e:
		if e.get_dbus_name() == 'org.freedesktop.PolicyKit.NotPrivilegedException':
		    if self.polkitauth(Exception.__str__(e)):
			repeat = True
		else:
		    self.error_dialog(str(e))
	    except Exception, e:
		self.error_dialog(str(e))

	self.check_status()
	return ret

    def toggle_overview_dialog(self):
	if self.overview_dialog:
	    self.overview_dialog.cancel()
	else:
	    self.check_status()
	    self.overview_dialog = OverviewDialog(self)

    def polkitauth(self, action):
	ok = False
	try:
	    agent = dbus.SessionBus().get_object("org.freedesktop.PolicyKit.AuthenticationAgent", "/")
	    ok = agent.ObtainAuthorization(action, dbus.UInt32(0), dbus.UInt32(os.getpid()));
	except dbus.DBusException, e:
	    if e.get_dbus_name() == 'org.freedesktop.DBus.Error.ServiceUnknown':
		self.error_dialog(_("The PolicyKit Authentication Agent is not available.\nTry installing 'PolicyKit-gnome'."))
	    else:
		raise
	return ok

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="%prog [options]")
    parser.add_option('--tray', dest="tray", action='store_true',
	    default=False, help="start as system tray icon")
    parser.add_option('--delay', dest="delay", metavar='N',
	    action='store', type='int', default=0,
	    help="when started in system tray, delay status query N seconds")

    (opts, args) = parser.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    app = fwzsApp(trayonly = opts.tray, delay=opts.delay);
    gtk.main()

# vim: sw=4 ts=8 noet
