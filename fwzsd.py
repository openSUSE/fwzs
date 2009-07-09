#!/usr/bin/python

import gobject

import dbus
import dbus.service
import dbus.mainloop.glib

import os
import subprocess

statusdir = '/var/run/SuSEfirewall2/status'
ifaceoverridedir = '/var/run/SuSEfirewall2/override/interfaces'

ZONES = {
    'int': 'Trusted Network',
    'dmz': 'Foreign Network',
    'ext': 'Internet',
}

class FirewallException(dbus.DBusException):
    _dbus_error_name = 'org.opensuse.zoneswitcher.FirewallException'

class ZoneSwitcher(dbus.service.Object):

    interface = "org.opensuse.zoneswitcher"

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{ss}')
    def Zones(self):
	zones = os.listdir(statusdir + '/zones')
	ret = {}
	for z in zones:
	    if z in ZONES:
		ret[z] = ZONES[z]
	    else:
		ret[z] = None

        return ret

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{ss}')
    def Interfaces(self):
	ifaces = os.listdir(statusdir + '/interfaces')
	ret = {}
	for i in ifaces:
	    ret[i] = self._get_zone(i)
        return ret

    def _get_zone(self, interface):
	    f = open(statusdir+'/interfaces/'+interface+'/zone')
	    z = f.readline()
	    return z[:len(z)-1]

    @dbus.service.method(interface,
                         in_signature='ss', out_signature='b')
    def setZone(self, interface, zone):
	if not os.access(statusdir+'/zones/'+zone, os.F_OK):
	    raise FirewallException
	if not os.access(statusdir+'/interfaces/'+interface, os.F_OK):
	    raise FirewallException
	dir = ifaceoverridedir+'/'+interface
	if not os.access(dir, os.F_OK):
	    os.makedirs(dir)
	f = open(dir+'/zone', 'w')
	print >>f, zone
	f.close()
	return True

    @dbus.service.method(interface,
                         in_signature='', out_signature='b')
    def Run(self):
	return subprocess.call(['/sbin/SuSEfirewall2']) == 0

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()
    name = dbus.service.BusName("org.opensuse.zoneswitcher", bus)
    object = ZoneSwitcher(bus, '/org/opensuse/zoneswitcher0')

    mainloop = gobject.MainLoop()
    mainloop.run()
