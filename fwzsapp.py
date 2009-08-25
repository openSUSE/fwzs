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

import gtk
import sys
from traceback import print_exc
from os import getpid

import dbus
import dbus.mainloop.glib

icon_green = ICONDIR + '/firewall.png'
icon_yellow = ICONDIR + '/firewall_y.png'
icon_red = ICONDIR + '/firewall_x.png'
icon_grey = ICONDIR + '/firewall_g.png'

class StatusIcon:

    def __init__(self, parent):
	self.icon = None
	self.parent = parent
	self.iconfile = icon_grey

    def show(self):
	self.icon = gtk.status_icon_new_from_file(icon_grey)
	self.icon.connect('popup-menu', lambda i, eb, et: self.parent.show_menu(i, eb, et))
#	self.icon.connect('activate', lambda *args: self.parent.show_settings())
	self._set_icon()

    def hide(self):
	# TODO
	self.icon = None

    def _set_icon(self):
	if self.icon:
	    self.icon.set_from_file(self.iconfile)

    def grey(self):
	self.iconfile = icon_grey
	self._set_icon()

    def green(self):
	self.iconfile = icon_green
	self._set_icon()

    def red(self):
	self.iconfile = icon_red
	self._set_icon()

    def yellow(self):
	self.iconfile = icon_yellow
	self._set_icon()


class Fwzsapp:

    def __init__(self, parent=None):
	self.bus = self.obj = self.iface = None
	self.icon = StatusIcon(self)
	self.check_status()
	self.dialog = None
	self.icon.show()

    def nameowner_changed_handler(self, name, old, new):
	if name != 'org.opensuse.zoneswitcher':
	    return
	
	if(not new and old):
	    self.obj = self.iface = None
	    self.icon.grey()
	    print "service exited"

	elif(not old and new):
	    print "service started"
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

		#print self.obj.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable")

	    except dbus.DBusException, e:
		self.obj = self.iface = None
		print "here:", str(e)
		return None

	return self.iface

    def _error_dialog(self, msg, title="Firewall Error"):
	d = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, msg)
	d.set_title(title)
	d.run()
	d.destroy()

    def _change_zone(self, item, iface, zone):
	if not item.get_active():
	    return

	repeat = True
	while repeat:
	    repeat = False
	    try:
		self.iface.setZone(iface, zone)
		self._run_firewall()
	    except dbus.DBusException, e:
		if e.get_dbus_name() == 'org.opensuse.zoneswitcher.FirewallNotPrivilegedException':
		    if self.polkitauth(Exception.__str__(e)):
			repeat = True
		else:
		    self._error_dialog(str(e))
	    except Exception, e:
		self._error_dialog(str(e))
		return

    def _run_firewall(self):
	ret = False
	repeat = True
	while repeat:
	    repeat = False
	    try:
		ret = self.iface.Run()
	    except dbus.DBusException, e:
		if e.get_dbus_name() == 'org.opensuse.zoneswitcher.FirewallNotPrivilegedException':
		    if self.polkitauth(Exception.__str__(e)):
			repeat = True
		else:
		    self._error_dialog(str(e))
	    except Exception, e:
		self._error_dialog(str(e))

	self.check_status()
	return ret

    def _menu_error(self, menu, txt):
	item = gtk.MenuItem(txt)
	item.set_sensitive(False)
	item.show()
	menu.append(item)

    def show_menu(self, icon, event_button, event_time):

	menu = gtk.Menu()
	self.check_status()

	if(not self.bus):
	    item = gtk.MenuItem("DBus not running")
	    item.set_sensitive(False)
	    item.show()
	    menu.append(item)

	    self.icon.grey()

	elif(not self.getzsiface()):
	    item = gtk.MenuItem("zoneswitcher service not running")
	    item.set_sensitive(False)
	    item.show()
	    menu.append(item)
	
	else:
	    zones = self.iface.Zones()

	    if zones:
		ifaces = self.iface.Interfaces()

		if ifaces:
		    item = gtk.MenuItem("Firewall interfaces")
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
		    item = gtk.MenuItem("No interfaces found.")
		    item.set_sensitive(False)
		    item.show()
		    menu.append(item)

	    else:
		self._menu_error(menu, "No zones found.\nFirewall not running or fwzs not supported?")

	    item = gtk.MenuItem("Run Firewall")
	    item.connect('activate', lambda *args: self._run_firewall())
	    item.show()
	    menu.append(item)

	item = gtk.SeparatorMenuItem()
	item.show()
	menu.append(item)

	item = gtk.MenuItem("Quit")
	item.connect('activate', lambda *args: gtk.main_quit())
	item.show()
	menu.append(item)

	menu.popup(None, None,
	    gtk.status_icon_position_menu, event_button,
	    event_time, icon)

    def show_settings(self):
	if self.dialog:
	    return
	self.dialog = gtk.Dialog("Firewall Zone Switcher", None, 0, ( gtk.STOCK_OK, gtk.RESPONSE_ACCEPT ))
	vbox = self.dialog.get_child()
	w = gtk.CheckButton("autostart")
	w.show()
	vbox.pack_end(w)
	self.dialog.show()
	self.dialog.connect('response', lambda *args: self.settings_response())

    def settings_response(self):
	self.dialog.destroy()
	self.dialog = None

    def polkitauth(self, action):
	ok = False
	try:
	    agent = dbus.SessionBus().get_object("org.freedesktop.PolicyKit.AuthenticationAgent", "/")
	    ok = agent.ObtainAuthorization(action, dbus.UInt32(0), dbus.UInt32(getpid()));
	except dbus.DBusException, e:
	    if e.get_dbus_name() == 'org.freedesktop.DBus.Error.ServiceUnknown':
		self._error_dialog("The PolicyKit Authentication Agent is not available.\nTry installing 'PolicyKit-gnome'.")
	    else:
		raise
	return ok

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    app = Fwzsapp();
    gtk.main()

# vim: sw=4 ts=8 noet
