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
from PolkitAuth import PolkitAuth

import os
import subprocess

import gettext

TIMEOUT = 60

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
	self.timeout = None
	self.mainloop = None
	self.clients = {}

    def _add_client(self, sender):
	if self.timeout:
	    gobject.source_remove(self.timeout)
	    self.timeout = None
	self.clients[sender] = 1

    def _update_timeout(self,):
	if not self.mainloop:
	    return
	if self.timeout:
	    gobject.source_remove(self.timeout)
	self.timeout = gobject.timeout_add(TIMEOUT * 1000, self._goodbye)

    def set_mainloop(self, l):
	self.mainloop = l

    def _goodbye(self):
	if len(self.clients):
	    print "clients != 0. Should not happen!", self.clients
	    return
	print "exit due to timeout"
	self.mainloop.quit()
	return False

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{ss}', sender_keyword='sender')
    def Zones(self, sender=None):
	"""Return {"ZONE": "human readable name", ... }"""
	self._add_client(sender)
	return self.impl.Zones(sender=sender)

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{ss}', sender_keyword='sender')
    def Interfaces(self, sender=None):
	"""Return {"INTERFACENAME": "ZONE", ... }"""
	self._add_client(sender)
	return self.impl.Interfaces(sender=sender)

    @dbus.service.method(interface,
                         in_signature='ss', out_signature='b', sender_keyword='sender', async_callbacks=('return_cb', 'error_cb'))
    def setZone(self, interface, zone, sender, return_cb, error_cb):
	"""Put the specified interface in the specified zone on next Firewall run
	Return True|False"""
	self._add_client(sender)
	self._check_polkit(sender, "org.opensuse.zoneswitcher.control",
		return_cb, error_cb,
		lambda interface, zone, sender: self.impl.setZone(interface, zone, sender), interface, zone, sender)

    @dbus.service.method(interface,
                         in_signature='', out_signature='b', sender_keyword='sender', async_callbacks=('return_cb', 'error_cb'))
    def Run(self, sender, return_cb, error_cb):
	"""Run the Firewall to apply settings.
	Return True|False"""
	self._add_client(sender)
	self._check_polkit(sender, "org.opensuse.zoneswitcher.control",
		return_cb, error_cb,
		lambda sender: self.impl.Run(sender), sender)

    @dbus.service.method(interface,
                         in_signature='', out_signature='b', sender_keyword='sender')
    def Status(self, sender=None):
	"""Status of backend
	Return running: True off:False
	exception on error"""
	self._add_client(sender)
	return self.impl.Status(sender=sender)

    @dbus.service.method(interface,
                         in_signature='s', out_signature='b', sender_keyword='sender')
    def setLang(self, lang, sender=None):
	self._add_client(sender)
	return self.impl.setLang(lang, sender=sender)

    def nameowner_changed_handler(self, name, old, new):
	if not new and old in self.clients:
	    del self.clients[old]
	    if len(self.clients) == 0:
		self._update_timeout()
	self.impl.nameowner_changed_handler(name, old, new)

    def _check_polkit(self, sender, action, return_cb, error_cb, func, *args ):
	#print return_cb, error_cb, func, args
	pk = PolkitAuth()
	pk.check(sender, action,
		lambda result: self._pk_auth_done(result, return_cb, error_cb, func, *args),
		lambda e: self._pk_auth_except(error_cb, e))

    def _pk_auth_done(self, result, return_cb, error_cb, func, *args):
	#print return_cb, error_cb, func, args
	r = False
	if(result):
	    try:
		r = func(*args)
	    except Exception, e:
		error_cb(e)
		return
		
	return_cb(r)

    def _pk_auth_except(self, error_cb, e):
	error_cb(e)

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
    object.set_mainloop(mainloop)
    mainloop.run()

# vim: sw=4 ts=8 noet
