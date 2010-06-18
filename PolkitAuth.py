#!/usr/bin/python

import dbus

class PolicyKitNotPrivilegedException(dbus.DBusException):
    _dbus_error_name = 'org.freedesktop.PolicyKit.NotPrivilegedException'

class PolkitAuth:

    def _pk1_result_is_authorized(self, r):
	auth = r[0]
	chal = r[1]
	adetail = r[2]
	return auth == True
    
    def _pk_result_is_authorized(self, action, r, reply_handler = None, error_handler = None):
	if (r and r == "yes"):
	    if(reply_handler != None):
		reply_handler(True)
	    else:
		return True
	
	if (error_handler != None):
	    error_handler(PolicyKitNotPrivilegedException(action))
	else:
	    raise PolicyKitNotPrivilegedException(action)

    def check(self, sender, action, reply_handler = None, error_handler = None):
	polkit1 = True
	try: 
	    pko = dbus.SystemBus().get_object("org.freedesktop.PolicyKit1",
					   "/org/freedesktop/PolicyKit1/Authority")
	except:
	    polkit1 = False

	if(polkit1):
	    pki = dbus.Interface(pko, "org.freedesktop.PolicyKit1.Authority")

	    subj = ("system-bus-name", { 'name': sender})
	    details = {}
	    flags = 1 # user interaction = 1, no user interaction = 0
	    cancelid = ""
	    if (reply_handler and error_handler):
		pki.CheckAuthorization(subj, action, details, flags, cancelid,
		    reply_handler=lambda result: reply_handler(self._pk1_result_is_authorized(result)), error_handler=error_handler)
		return
	    else:
		r = pki.CheckAuthorization(subj, action, details, flags, cancelid)
		return self._pk1_result_is_authorized(r)
	else:
	    print "try polit"
	    pko = dbus.SystemBus().get_object("org.freedesktop.PolicyKit", "/")
	    pki = dbus.Interface(pko, "org.freedesktop.PolicyKit")
	    if (reply_handler and error_handler):
		pki.IsSystemBusNameAuthorized(action, sender, True,
		    reply_handler=lambda result: self._pk_result_is_authorized(action, result, reply_handler, error_handler), error_handler=error_handler)
	    else:
		result = pki.IsSystemBusNameAuthorized(action, sender, True)
		return self._pk_result_is_authorized(action, result)
