#!/usr/bin/python

import gobject

import dbus
import dbus.service
import dbus.mainloop.glib

import os
import subprocess

class FirewallException(dbus.DBusException):
    _dbus_error_name = 'org.opensuse.zoneswitcher.FirewallException'

class ZoneSwitcher(dbus.service.Object):
    """Base class for zone switcher implementation"""

    interface = "org.opensuse.zoneswitcher"

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{ss}')
    def Zones(self):
	"""Return {"ZONE": "human readable name", ... }"""
	raise FirewallException("not implemented")

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{ss}')
    def Interfaces(self):
	"""Return {"INTERFACENAME": "ZONE", ... }"""
	raise FirewallException("not implemented")

    @dbus.service.method(interface,
                         in_signature='ss', out_signature='b')
    def setZone(self, interface, zone):
	"""Put the specified interface in the specified zone on next Firewall run
	Return True|False"""
	raise FirewallException("not implemented")

    @dbus.service.method(interface,
                         in_signature='', out_signature='b')
    def Run(self):
	"""Run the Firewall to apply settings.
	Return True|False"""
	raise FirewallException("not implemented")

class ZoneSwitcherSuSEfirewall2(ZoneSwitcher):

    ZONES = {
	'int': 'Trusted Network',
	'dmz': 'Foreign Network',
	'ext': 'Internet',
    }

    STATUSDIR = '/var/run/SuSEfirewall2/status'
    IFACEOVERRIDEDIR = '/var/run/SuSEfirewall2/override/interfaces'

    def Zones(self):
	zones = os.listdir(self.STATUSDIR + '/zones')
	ret = {}
	for z in zones:
	    if z in self.ZONES:
		ret[z] = self.ZONES[z]
	    else:
		ret[z] = None

        return ret

    def Interfaces(self):
	ifaces = os.listdir(self.STATUSDIR + '/interfaces')
	ret = {}
	for i in ifaces:
	    ret[i] = self._get_zone(i)
        return ret

    def _get_zone(self, interface):
	    f = open(self.STATUSDIR+'/interfaces/'+interface+'/zone')
	    z = f.readline()
	    return z[:len(z)-1]

    def setZone(self, interface, zone):
	if not os.access(self.STATUSDIR+'/zones/'+zone, os.F_OK):
	    raise FirewallException
	if not os.access(self.STATUSDIR+'/interfaces/'+interface, os.F_OK):
	    raise FirewallException
	dir = self.IFACEOVERRIDEDIR+'/'+interface
	if not os.access(dir, os.F_OK):
	    os.makedirs(dir)
	f = open(dir+'/zone', 'w')
	print >>f, zone
	f.close()
	return True

    def Run(self):
	return subprocess.call(['/sbin/SuSEfirewall2']) == 0

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()
    name = dbus.service.BusName("org.opensuse.zoneswitcher", bus)
    object = ZoneSwitcherSuSEfirewall2(bus, '/org/opensuse/zoneswitcher0')

    mainloop = gobject.MainLoop()
    mainloop.run()
