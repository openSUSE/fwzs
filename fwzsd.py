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

import gettext

def N_(x): return x

class FirewallException(dbus.DBusException):
    _dbus_error_name = 'org.opensuse.zoneswitcher.FirewallException'

class FirewallNotPrivilegedException(dbus.DBusException):
    _dbus_error_name = 'org.opensuse.zoneswitcher.FirewallNotPrivilegedException'

# backends need to implement this class
class ZoneSwitcher:

    def __init__(self, *args):
	self.trans = {}

    def Zones(self, sender=None):
	raise FirewallException("not implemented")

    def Interfaces(self, sender=None):
	raise FirewallException("not implemented")

    def setZone(self, interface, zone, sender=None):
	raise FirewallException("not implemented")

    def Run(self, sender=None):
	raise FirewallException("not implemented")

    def Status(self, sender=None):
	raise FirewallException("not implemented")

    def setLang(self, lang, sender=None):
	return self._setlang(lang, sender=sender)

    def _setlang(self, lang, domain="fwzsd", sender=None):
	# yet another hack. We remember the language per connection
	try:
	    t = gettext.translation(domain=domain, languages=[lang])
	    self.trans[sender] = t
	    return True
	except Exception, e:
	    print e
	return False

    def nameowner_changed_handler(self, name, old, new):
	if old and not new and old in self.trans:
	    del self.trans[old]

class ZoneSwitcherDBUS(dbus.service.Object):
    """DBUS interface for zone switcher"""

    interface = "org.opensuse.zoneswitcher"

    def __init__(self, impl, *args):
	dbus.service.Object.__init__(self, *args) 
	self.impl = impl
	self._connection.add_signal_receiver(
			lambda name, old, new: self.nameowner_changed_handler(name, old, new),
			dbus_interface='org.freedesktop.DBus',
			signal_name='NameOwnerChanged')

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{ss}', sender_keyword='sender')
    def Zones(self, sender=None):
	"""Return {"ZONE": "human readable name", ... }"""
	return self.impl.Zones(sender=sender)

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{ss}', sender_keyword='sender')
    def Interfaces(self, sender=None):
	"""Return {"INTERFACENAME": "ZONE", ... }"""
	return self.impl.Interfaces(sender=sender)

    @dbus.service.method(interface,
                         in_signature='ss', out_signature='b', sender_keyword='sender')
    def setZone(self, interface, zone, sender=None):
	"""Put the specified interface in the specified zone on next Firewall run
	Return True|False"""
	self._check_polkit(sender)
	return self.impl.setZone(interface, zone, sender)

    @dbus.service.method(interface,
                         in_signature='', out_signature='b', sender_keyword='sender')
    def Run(self, sender=None):
	"""Run the Firewall to apply settings.
	Return True|False"""
	self._check_polkit(sender)
	return self.impl.Run(sender)

    @dbus.service.method(interface,
                         in_signature='', out_signature='b', sender_keyword='sender')
    def Status(self, sender=None):
	"""Status of backend
	Return running: True off:False
	exception on error"""
	return self.impl.Status(sender=sender)

    @dbus.service.method(interface,
                         in_signature='s', out_signature='b', sender_keyword='sender')
    def setLang(self, lang, sender=None):
	return self.impl.setLang(lang, sender=sender)

    def nameowner_changed_handler(self, name, old, new):
	self.impl.nameowner_changed_handler(name, old, new)

    def _check_polkit(self, sender, action = "org.opensuse.zoneswitcher.control"):
	try:
	    pko = self._connection.get_object("org.freedesktop.PolicyKit", "/")
	    pki = dbus.Interface(pko, "org.freedesktop.PolicyKit")
	    result = pki.IsSystemBusNameAuthorized(action, sender, True)
	    if result and result == "yes":
		return True
	except Exception, e:
	    raise e

	raise FirewallNotPrivilegedException(action)

class ZoneSwitcherSuSEfirewall2(ZoneSwitcher):

    ZONES = {
	'int': N_('Not Protected'),
	'dmz': N_('Partially Protected'),
	'ext': N_('Protected'),
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

    def Zones(self, sender=None):
	ret = {}

	for z in self._listzones():
	    if z in self.ZONES:
		ret[z] = self.ZONES[z]
		if sender in self.trans:
		    ret[z] = self.trans[sender].gettext(ret[z])
	    else:
		ret[z] = None

        return ret

    def Interfaces(self, sender=None):
	ret = {}

	for i in self._listiterfaces():
	    ret[i] = self._get_zone(i)
        return ret

    def _get_zone(self, interface):
	try:
	    f = open(self.STATUSDIR+'/interfaces/'+interface+'/zone')
	    z = f.readline()
	    return z[:len(z)-1]
	except:
	    return ""

    def setZone(self, interface, zone, sender=None):
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

    def Run(self, sender=None):
	try:
	    if(subprocess.call(['/sbin/SuSEfirewall2']) != 0):
		raise FirewallException("SuSEfirewall2 failed")
	except:
	    raise FirewallException("can't run SuSEfirewall2")

    def Status(self, sender=None):
	try:
	    if(subprocess.call(['/etc/init.d/SuSEfirewall2_setup', 'status']) == 0):
		return True
	    return False
	except:
	    raise FirewallException("SuSEfirewall2 status unknown")

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()
    name = dbus.service.BusName("org.opensuse.zoneswitcher", bus)
    object = ZoneSwitcherDBUS(ZoneSwitcherSuSEfirewall2(), bus, '/org/opensuse/zoneswitcher0')

    mainloop = gobject.MainLoop()
    mainloop.run()

# vim: sw=4 ts=8 noet
