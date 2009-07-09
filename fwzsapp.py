#!/usr/bin/python

ICONDIR = '.' # +++automake+++

import gtk
import sys
from traceback import print_exc

import dbus
import dbus.mainloop.glib

ICON = ICONDIR + '/firewall.png'

class StatusIcon:

    def __init__(self, parent=None):
	self.bus = self.obj = self.iface = None
	self.getzsiface()
	self.icon = gtk.status_icon_new_from_file(ICON)
	self.icon.connect('popup-menu', lambda i, eb, et: self.show_menu(i, eb, et))
	self.icon.connect('activate', lambda *args: self.getzsiface())

    def nameowner_changed_handler(self, name, old, new):
	if name != 'org.opensuse.zoneswitcher':
	    return
	
	if(not new and old):
	    self.obj = self.iface = None
	    self.icon.set_from_stock(gtk.STOCK_DIALOG_ERROR)
	    print "service exited"

	elif(not old and new):
	    print "service started"
	    self.getzsiface()
	    self.icon.set_from_file(ICON)

    def catchall_handler(self, *args, **kwargs):
	print "args: ", args
	print "kwargs: ", kwargs

    def bus_disconnected(self):
	print "bus disconnected"
	self.bus = self.obj = self.iface = None
	self.icon.set_from_stock(gtk.STOCK_DIALOG_ERROR)

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


    def _change_zone(self, item, iface, zone):
	if not item.get_active():
	    return

	self.iface.setZone(iface, zone)
	self.iface.Run()

    def show_menu(self, icon, event_button, event_time):

	menu = gtk.Menu()

	if(not self.bus):
	    item = gtk.MenuItem("DBus not running")
	    item.set_sensitive(False)
	    item.show()
	    menu.append(item)

	    icon.set_from_stock(gtk.STOCK_DIALOG_ERROR)

	elif(not self.getzsiface()):
	    item = gtk.MenuItem("zoneswitcher service not running")
	    item.set_sensitive(False)
	    item.show()
	    menu.append(item)

	    icon.set_from_stock(gtk.STOCK_DIALOG_ERROR)
	
	else:
	    item = gtk.MenuItem("Firewall interfaces")
	    item.set_sensitive(False)
	    item.show()
	    menu.append(item)

	    zones = self.iface.Zones()
	    ifaces = self.iface.Interfaces()

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

		icon.set_from_file(ICON)

	item = gtk.MenuItem("Quit")
	item.connect('activate', lambda *args: gtk.main_quit())
	item.show()
	menu.append(item)

	menu.popup(None, None,
	    gtk.status_icon_position_menu, event_button,
	    event_time, icon)

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    icon = StatusIcon();
    gtk.main()
