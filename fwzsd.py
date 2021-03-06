#!/usr/bin/python
#
# fwzsd - fwzs daemon
# Copyright (C) 2009 SUSE LINUX Products GmbH
# Copyright (C) 2015 SUSE LLC
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

timer = None

def N_(x): return x

_debug_level = 0
def debug(level, msg):
    if (level <= _debug_level):
	print level, msg

class FirewallException(dbus.DBusException):
    _dbus_error_name = 'org.opensuse.zoneswitcher.FirewallException'

class FirewallNotPrivilegedException(dbus.DBusException):
    _dbus_error_name = 'org.opensuse.zoneswitcher.FirewallNotPrivilegedException'

# backends need to implement this class
class ZoneSwitcher(gobject.GObject):

    __gsignals__ = {
	'ZoneChanged':
	    (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_STRING,gobject.TYPE_STRING,)),
	'HasRun':
	    (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, *args):
	self.__gobject_init__()
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

    def do_ZoneChanged(self, iface, zone):
	return

    def do_HasRun(self):
	return

# the DBus interface
class ZoneSwitcherDBUS(dbus.service.Object):
    """DBUS interface for zone switcher"""

    SUPPORTS_MULTIPLE_OBJECT_PATHS = True

    interface = "org.opensuse.zoneswitcher"
    firewalld_interface = "org.fedoraproject.FirewallD1.zone"

    def __init__(self, impl):
	bus = dbus.SystemBus()
	dbus.service.Object.__init__(self, conn = bus)

	self.names = [
	    dbus.service.BusName("org.opensuse.zoneswitcher", bus),
	    dbus.service.BusName("org.fedoraproject.FirewallD1", bus),
	    ]

	self.add_to_connection(bus, '/org/opensuse/zoneswitcher0')
	self.add_to_connection(bus, "/org/fedoraproject/FirewallD1")

	self.impl = impl
	impl.connect('ZoneChanged', lambda obj, iface, zone: self._zone_changed_receive(iface, zone))
	impl.connect('HasRun', lambda obj: self._has_run_received())
	self._connection.add_signal_receiver(
			lambda name, old, new: self.nameowner_changed_handler(name, old, new),
			bus_name='org.freedesktop.DBus',
			dbus_interface='org.freedesktop.DBus',
			signal_name='NameOwnerChanged')
	self.mainloop = None
	self.clients = {}

    def _add_client(self, sender):
	if (not sender in self.clients):
	    debug(1, "add client %s"%sender)
	    self.clients[sender] = 1
	    self._update_timeout()

    def _remove_client(self, sender):
	if (sender in self.clients):
	    debug(1,"remove client %s"%sender)
	    del self.clients[sender]
	    self._update_timeout()

    def _update_timeout(self,):
	global timer
	timer.inhibit("dbusiface", len(self.clients) != 0)

    def set_mainloop(self, l):
	self.mainloop = l

    @dbus.service.method(interface,
                         in_signature='', out_signature='a{sa{ss}}', sender_keyword='sender')
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

    @dbus.service.signal(interface, signature='ss')
    def ZoneChanged(self, iface, zone):
	return

    @dbus.service.signal(interface, signature='')
    def HasRun(self):
	return

    def _zone_changed_receive(self, iface, zone):
	if not iface:
	    return
	if not zone:
	    zone = ''
	debug(1,"DBUS: forwarding ZoneChanged(%s, %s)"%(iface, zone))
	self.ZoneChanged(iface, zone)

    def _has_run_received(self):
	debug(1,"DBUS: forwarding HasRun()")
	self.HasRun()

    def nameowner_changed_handler(self, name, old, new):
	if not new and old in self.clients:
	    self._remove_client(old)
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
	else:
		error_cb(FirewallException(N_("You are not authorized.")))
		
	return_cb(r)

    def _pk_auth_except(self, error_cb, e):
	error_cb(e)

    def _firewalld_set_zone(self, dev, name, sender, return_cb, error_cb):

	self._check_polkit(sender, "org.opensuse.zoneswitcher.control",
		return_cb, error_cb,
		lambda: self._firewalld_set_zone_cb(dev, name, sender))

    def _firewalld_set_zone_cb(self, dev, name, sender):

	zone = None

	# need to get a reverse map name -> zone here
	d = { v['desc']: k for k, v in self.impl.Zones().items() }

	if not name in d:
	    if name:
		print _("specified zone '{}' is invalid").format(name)
	else:
	    zone = d[name]

	self.impl.setZone(dev, zone, sender)
	if (self.impl.Status()):
	    self.impl.Run()
	return zone or ''

    @dbus.service.method(firewalld_interface,
                         in_signature='ss', out_signature='s',
			 sender_keyword='sender',
			 async_callbacks=('return_cb', 'error_cb'))
    def addInterface(self, zone, dev, sender, return_cb, error_cb):
	debug(1, "firewalld addInterface {} -> '{}'".format(dev, zone))
	self._add_client(sender)
	self._firewalld_set_zone(dev, zone, sender, return_cb, error_cb)
	return self.impl.Interfaces()[dev] or None

    @dbus.service.method(firewalld_interface,
                         in_signature='ss', out_signature='s',
			 sender_keyword='sender',
			 async_callbacks=('return_cb', 'error_cb'))
    def changeZone(self, zone, dev, sender, return_cb, error_cb):
	return self.changeZoneOfInterface(zone, dev, sender, return_cb, error_cb)

    @dbus.service.method(firewalld_interface,
                         in_signature='ss', out_signature='s',
			 sender_keyword='sender',
			 async_callbacks=('return_cb', 'error_cb'))
    def changeZoneOfInterface(self, zone, dev, sender, return_cb, error_cb):
	debug(1, "firewalld changeZoneOfInterface {} -> '{}'".format(dev, zone))
	self._add_client(sender)
	self._firewalld_set_zone(dev, zone, sender, return_cb, error_cb)
	return self.impl.Interfaces()[dev] or None

    @dbus.service.method(firewalld_interface,
                         in_signature='ss', out_signature='s',
			 sender_keyword='sender',
			 async_callbacks=('return_cb', 'error_cb'))
    def removeInterface(self, zone, dev, sender, return_cb, error_cb):
	debug(1, "firewalld removeInterface {} -> '{}'".format(dev, zone))
	self._add_client(sender)
	z = self.impl.Interfaces()[dev] or None
	self._firewalld_set_zone(dev, zone, sender, return_cb, error_cb)
	return z

    @dbus.service.method(firewalld_interface,
                         in_signature=None, out_signature='as', sender_keyword='sender')
    def getZones(self, sender):
	self._add_client(sender)
	debug(1, "firewalld getZones")
	return [i['desc'] for i in self.impl.Zones(sender=sender).values()]

# zone switcher implementation for SuSEfirewall2
class ZoneSwitcherSuSEfirewall2(ZoneSwitcher):

    ZONES = {
	'int': N_('Private Network'),
	'dmz': N_('DMZ'),
	'ext': N_('Public Network'),
    }

    STATUSDIR = '/var/run/SuSEfirewall2/status'
    IFACEOVERRIDEDIR = '/var/run/SuSEfirewall2/override/interfaces'

    def _listzones(self):
	try:
	    return os.listdir(self.STATUSDIR + '/zones')
	except Exception, e:
	    print e
	    return []

    def _listiterfaces(self):
	try:
	    # consider all system devices valid as SuSEfirewall2 may not know
	    # about all yet
	    return [ d for d in os.listdir("/sys/class/net/") if d != 'lo' and d != 'sit0' ]
	    #return os.listdir(self.STATUSDIR + '/interfaces')
	except Exception, e:
	    print e
	    return []

    def Zones(self, sender=None):
	ret = {}

	for z in self._listzones():
	    ret[z] = { 'desc' : '' }
	    if z in self.ZONES:
		ret[z]['desc'] = self.ZONES[z]
		if sender in self.trans:
		    ret[z]['desc'] = self.trans[sender].gettext(ret[z]['desc'])

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
	    raise FirewallException(_("specified interface is invalid"))
	if zone and not zone in self._listzones():
	    raise FirewallException(_("specified zone is invalid"))

	dir = self.IFACEOVERRIDEDIR+'/'+interface
	if not os.access(dir, os.F_OK):
	    os.makedirs(dir)
	file = dir+'/zone'
	if (zone):
	    f = open(file, 'w')
	    print >>f, zone
	    f.close()
	else:
	    if os.access(file, os.F_OK):
		os.unlink(file)

	self.emit("ZoneChanged", interface, zone)
	return True

    def Run(self, sender=None):
	try:
	    if(subprocess.call(['/sbin/SuSEfirewall2']) != 0):
		raise FirewallException("SuSEfirewall2 failed")
	except:
	    raise FirewallException("can't run SuSEfirewall2")
	self.emit("HasRun")
	return True

    def Status(self, sender=None):
	try:
	    #n = open('/dev/null', 'w')
	    #if(subprocess.call(['/sbin/SuSEfirewall2', 'status'], stdout=n, stderr=n) == 0):
	    if (os.access(self.STATUSDIR, os.F_OK)):
		return True
	    return False
	except Exception, e:
	    print e
	    raise FirewallException("SuSEfirewall2 status unknown")


class NMWatcher(gobject.GObject):

    DEVSTATES = {
	      0: 'UNKNOWN',
	     10: 'UNMANAGED',
	     20: 'UNAVAILABLE',
	     30: 'DISCONNECTED',
	     40: 'PREPARE',
	     50: 'CONFIG',
	     60: 'NEED_AUTH',
	     70: 'IP_CONFIG',
	     80: 'IP_CHECK',
	     90: 'SECONDARIES',
	    100: 'ACTIVATED',
	    110: 'DEACTIVATING',
	    120: 'FAILED',
	    }

    STATEDIR = "/var/lib/zoneswitcher"

    def __init__(self, switcher):
	self.bus = dbus.SystemBus()
	self.proxy = None
	self.manager = None
	self.running = False
	self.devuuid = {} # devname => uuid
	self.zones = {} # uuid => zone
	self.switcher = switcher
	self.devicewatchers = {}
	self.ifacedirty = {} # map of interfaces that have changed zones but no fw run yet

	# XXX: start is probably racy if NM does something here already
	self.readstate()

	switcher.connect('ZoneChanged', lambda obj, iface, zone: self._zone_changed_receive(iface, zone))
	switcher.connect('HasRun', lambda obj: self._has_run_received())

	self.check_status()
	self.applystate()

	self.bus.add_signal_receiver(
	    lambda name, old, new: self.nameowner_changed_handler(name, old, new),
		bus_name='org.freedesktop.DBus',
		dbus_interface='org.freedesktop.DBus',
		signal_name='NameOwnerChanged')

	self.bus.add_signal_receiver(
	    lambda device, **kwargs: self.device_add_rm(device, True, **kwargs),
		bus_name='org.freedesktop.NetworkManager',
		dbus_interface = 'org.freedesktop.NetworkManager',
		signal_name = 'DeviceAdded',
		sender_keyword = 'sender')

	self.bus.add_signal_receiver(
	    lambda device, **kwargs: self.device_add_rm(device, False, **kwargs),
		bus_name='org.freedesktop.NetworkManager',
		dbus_interface = 'org.freedesktop.NetworkManager',
		signal_name = 'DeviceRemoved',
		sender_keyword = 'sender')

	if not os.access(self.STATEDIR, os.F_OK):
	    os.makedirs(self.STATEDIR)

    def cleanup(self):
	self.switcher = None

    def savestate(self):
	debug(1,"save state")
	file = self.STATEDIR + "/nmwatcher.zones"
	f = open(file, 'w')
	for uuid in self.zones.keys():
	    print >>f, "%s %s"%(uuid, self.zones[uuid])
	f.close()

    def readstate(self):
	debug(1,"read state")
	file = self.STATEDIR + "/nmwatcher.zones"
	if not os.access(file, os.F_OK):
	    return
	f = open(file, 'r')
	if (f):
	    line = f.readline()
	    while(line):
		a = line.split('\n')[0].split(' ')
		if (len(a) == 2):
		    debug(1,"%s -> %s"%(a[0], a[1]))
		    self.zones[a[0]] = a[1]
		line = f.readline()
	    f.close()

    def applystate(self):
	didsomething = False
	for name in self.devuuid:
	    uuid = self.devuuid[name]
	    try:
		if uuid in self.zones:
		    z = self.zones[uuid]
		    if z != self.switcher._get_zone(name):
			self.switcher.setZone(name, z)
			didsomething = True
	    except FirewallException, e:
		print e

	if (didsomething and self.switcher.Status()):
	    self.switcher.Run()

    def devstate2name(self, state):
	if state in self.DEVSTATES:
	    return self.DEVSTATES[state]
	return "UNKNOWN:%s"%state

    def nameowner_changed_handler(self, name, old, new):
	if name != 'org.freedesktop.NetworkManager':
	    return
	
	off = old and not new
	self.check_status(off)

    def device_add_rm(self, device, added, sender=None, **kwargs):
	if (added):
	    self.watch_device(device)
	else:
	    debug(1,"device %s removed"%device)
	    if (device in self.devicewatchers):
		self.devicewatchers[device].remove()
		del self.devicewatchers[device]

    def device_state_changed_handler(self, props, name, new, old, reason, **kwargs):
	uuid = None
	try:
	    conn_path = props.Get("org.freedesktop.NetworkManager.Device", "ActiveConnection")
	    uuid = self.activeconn_get_uuid(conn_path)
	except dbus.DBusException, e:
	    pass
	debug(1,"%s: state change %s -> %s" % (name, self.devstate2name(old), self.devstate2name(new)))
	needchange = False
	if (not name in self.devuuid):
	    debug(1,"%s: new uuid %s"%(name, uuid))
	    needchange = True
	elif (self.devuuid[name] != uuid):
	    debug(1,"%s: uuid change %s -> %s"%(name, self.devuuid[name], uuid))
	    needchange = True
	    # save previously used zone in case it changed
	    if self.devuuid[name]:
		self.check_and_save(name, self.devuuid[name])

	if (needchange):
	    self.devuuid[name] = uuid
	    try:
		z = None
		if (uuid and uuid in self.zones):
		    z = self.zones[uuid]
		debug(1,"%s: setting zone to %s"%(name, z))
		self.switcher.setZone(name, z)
		if (self.switcher.Status()):
		    self.switcher.Run()
	    except FirewallException, e:
		print e

	    #if (uuid):
		#self.check_and_save(name, uuid)

	    #self.devuuid[name] = uuid

    def check_and_save(self, name, uuid):
	    if not uuid:
		debug(1,"BUG: check_and_save called with None uuid")
		return
	    z = self.switcher._get_zone(name)
	    if (z == ""):
		z = None
	    if (z and (not uuid in self.zones or self.zones[uuid] != z)):
		debug(1,"%s: new zone %s"%(uuid, z))
		self.zones[uuid] = z
		self.savestate()

    def _connect_nm(self):
	try:
	    self.proxy = self.bus.get_object("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
	    self.manager = manager = dbus.Interface(self.proxy, "org.freedesktop.NetworkManager")
	    running = True
	except dbus.DBusException, e:
	    running = False

	return running

    def check_status(self, force_off=False):
	if (force_off):
	    running = False
	else:
	    running = self.running
	    if (not self.manager):
		running = self._connect_nm()

	if (running):
	    if (not self.running):
		devices = self.manager.GetDevices()
		for d in devices:
		    self.watch_device(d)

	if (not running):
	    self.proxy = self.manager = None
	    self.devices = None
	    for d in self.devicewatchers:
		self.devicewatchers[d].remove()
	    self.devicewatchers = {}

	self.running = running
	debug(1,"NM Running: %s"%self.running)
	global timer
	timer.inhibit("nm", running)
	return

    def activeconn_get_uuid(self, path):
	try:
	    if (path != '/'):
		conn = self.bus.get_object("org.freedesktop.NetworkManager", path)
		return conn.Get( "org.freedesktop.NetworkManager.Connection.Active", "Uuid",
			dbus_interface="org.freedesktop.DBus.Properties")
	except dbus.DBusException, e:
	    pass
	return None

    def watch_device(self, d):
	# already watched. could happen if NM restarts and we both query all
	# devices and receive device add signals.
	if (d in self.devicewatchers):
	    return

	dev = self.bus.get_object("org.freedesktop.NetworkManager", d)
	props = dbus.Interface(dev, "org.freedesktop.DBus.Properties")
	name = props.Get("org.freedesktop.NetworkManager.Device", "Interface")
	state = props.Get("org.freedesktop.NetworkManager.Device", "State")
	conn_path = props.Get("org.freedesktop.NetworkManager.Device", "ActiveConnection")

	uuid = self.activeconn_get_uuid(conn_path)

	self.devuuid[name] = uuid

	debug(1,"Watching %s, state %s, uuid %s" % (name, self.devstate2name(state), uuid))
	self.devicewatchers[d] = self.bus.add_signal_receiver(
		lambda new, old, reason, **kwargs: self.device_state_changed_handler(props, name, new, old, reason, **kwargs),
		    bus_name='org.freedesktop.NetworkManager',
		    dbus_interface = 'org.freedesktop.NetworkManager.Device',
		    signal_name = 'StateChanged',
		    path = d, sender_keyword = 'sender')
	## XXX: not sure why setZone was needed here:
#	try:
#	    self.switcher.setZone(name, None)
#	except FirewallException, e:
#	    print e
    def _zone_changed_receive(self, iface, zone):
	if not iface:
	    return
	debug(1,"zone change on %s, marking dirty"%iface)
	self.ifacedirty[iface] = 1

    def _has_run_received(self):
	debug(1,"has run received")
	if len(self.ifacedirty):
	    for name in self.ifacedirty.keys():
		if self.devuuid[name]:
		    self.check_and_save(name, self.devuuid[name])
	    self.ifacedirty = {}

class Timer:

    def __init__(self, mainloop):
	self.timeout = None
	self.mainloop = mainloop
	self.inhibitors = {}

	self._start()

    def inhibit(self, who, doit):
	if (doit):
	    self.inhibitors[who] = 1
	    debug(1,"inhibitor %s added"%who)
	elif (who in self.inhibitors):
	    del self.inhibitors[who]
	    debug(1,"inhibitor %s removed"%who)

	if len(self.inhibitors) == 0:
	    self._start()
	else:
	    if self.timeout:
		gobject.source_remove(self.timeout)
		debug(1,"timer deleted")

    def _start(self):
	    if self.timeout:
		gobject.source_remove(self.timeout)
	    self.timeout = gobject.timeout_add(TIMEOUT * 1000, self._goodbye)
	    debug(1,"new timer installed")

    def _goodbye(self):
	if len(self.inhibitors):
	    debug(1,"inhibitors != 0. Should not happen!", self.inhibitors)
	    return True
	debug(1,"exit due to timeout")
	self.mainloop.quit()
	return False

if __name__ == '__main__':

    from optparse import OptionParser

    parser = OptionParser(usage="%prog [options]")
    parser.add_option('--debug', dest="debug", metavar='N',
	    action='store', type='int', default=0,
	    help="debug level")

    (opts, args) = parser.parse_args()
    if opts.debug:
	_debug_level = opts.debug

    gettext.install('fwzsd')

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    mainloop = gobject.MainLoop()

    timer = Timer(mainloop)

    if os.access("/etc/sysconfig/SuSEfirewall2", os.F_OK):
	switcher = ZoneSwitcherSuSEfirewall2()
    else:
	print "Unsupported Firewall"
	import sys
	sys.exit(1)

    dbusinterface = ZoneSwitcherDBUS(switcher)

    nm = NMWatcher(switcher)

    dbusinterface.set_mainloop(mainloop)
    mainloop.run()

# vim: sw=4 ts=8 noet
