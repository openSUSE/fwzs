#!/usr/bin/python
#
# fwzsd - fwzs daemon
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

    def _listzones(self):
	try:
	    return os.listdir(self.STATUSDIR + '/zones')
	except:
	    return []

    def _listiterfaces(self):
	try:
	    return os.listdir(self.STATUSDIR + '/interfaces')
	except:
	    return []

    def Zones(self):
	ret = {}

	for z in self._listzones():
	    if z in self.ZONES:
		ret[z] = self.ZONES[z]
	    else:
		ret[z] = None

        return ret

    def Interfaces(self):
	ret = {}

	for i in self._listiterfaces():
	    ret[i] = self._get_zone(i)
        return ret

    def _get_zone(self, interface):
	    f = open(self.STATUSDIR+'/interfaces/'+interface+'/zone')
	    z = f.readline()
	    return z[:len(z)-1]

    def setZone(self, interface, zone):
	# check user supplied strings
	if not interface in self._listiterfaces():
	    raise FirewallException("specified interface is invalid")
	if not zone in self._listzones():
	    raise FirewallException("specified zone is invalid")

	dir = self.IFACEOVERRIDEDIR+'/'+interface
	if not os.access(dir, os.F_OK):
	    os.makedirs(dir)
	f = open(dir+'/zone', 'w')
	print >>f, zone
	f.close()
	return True

    def Run(self):
	try:
	    if(subprocess.call(['/sbin/SuSEfirewall2']) != 0):
		raise FirewallException("SuSEfirewall2 failed")
	except:
	    raise FirewallException("can't run SuSEfirewall2")

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()
    name = dbus.service.BusName("org.opensuse.zoneswitcher", bus)
    object = ZoneSwitcherSuSEfirewall2(bus, '/org/opensuse/zoneswitcher0')

    mainloop = gobject.MainLoop()
    mainloop.run()

# vim: sw=4 ts=8 noet
