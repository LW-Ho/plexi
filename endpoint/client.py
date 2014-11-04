__author__ = "George Exarchakos"
__version__ = "0.0.9"
__email__ = "g.exarchakos@tue.nl"
__credits__ = ["XYZ"]
__copyright__ = "Copyright 2014, The RICH Project"
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from coapthon2 import defines
from coapthon2.client.coap_protocol import CoAP
from util.exception import FormatError, RequestError
from util.warn import deprecated
from twisted.internet import error
from twisted.internet import reactor
import netaddr
import time
import txthings.coap as coap
import txthings.resource as resource

coap.ACK_TIMEOUT = 10
coap.DEFAULT_BLOCK_SIZE_EXP = 3  # Block size 128
"""Default size exponent for blockwise transfers."""


class Communicator(object):

	def __init__(self):
		self.tickets = {}

	def start(self):
		try:
			reactor.run()
		except error.ReactorAlreadyRunning:
			pass

	def token(self, ticket):
		return self.tickets[ticket] if ticket in self.tickets else None

	def request(self, to_node, operation, uri, token, callback, payload='', kwargs=None):
		request = coap.Message(mtype=coap.CON, code=operation if operation != coap.OBSERVE else coap.GET, token=token, payload=payload)
		request.opt.uri_path = uri.split('/')
		request.remote = (to_node.ip, to_node.port)
		#request.opt.accept = coap.media_types_rev['application/json']
		#request.opt.content_format = coap.media_types_rev['application/json']
		protocol = coap.Coap(resource.Endpoint(None))
		ver = netaddr.IPAddress(to_node.ip).version
		#print(to_node.ip)
		if ver == 6:
			reactor.listenUDP(0, protocol, interface='::')
		else:
			reactor.listenUDP(0, protocol)
		if operation == coap.OBSERVE:
			request.opt.observe = 0
			requester = coap.Requester(protocol, request, observeCallback=callback, block1Callback=None, block2Callback=None, observeCallbackArgs=None, block1CallbackArgs=None, block2CallbackArgs=None, observeCallbackKeywords=None, block1CallbackKeywords=None, block2CallbackKeywords=None)
		else:
			requester = coap.Requester(protocol, request, observeCallback=None, block1Callback=None, block2Callback=None, observeCallbackArgs=None, block1CallbackArgs=None, block2CallbackArgs=None, observeCallbackKeywords=None, block1CallbackKeywords=None, block2CallbackKeywords=None)
		requester.deferred.addCallback(callback)
		self.tickets[requester.app_request.token] = token

	def GET(self, to_node, uri, token, callback):
		reactor.callWhenRunning(self.request, to_node, coap.GET, uri, token, callback)

	def OBSERVE(self, to_node, uri, token, callback):
		reactor.callWhenRunning(self.request, to_node, coap.OBSERVE, uri, token, callback)

	def POST(self, to_node, uri, payload, token, callback):
		reactor.callWhenRunning(self.request, to_node, coap.POST, uri, token, callback, payload)

	def DELETE(self, to_node, uri, token, callback):
		reactor.callWhenRunning(self.request, to_node, coap.GET, uri, token, callback)

	def test_callable(self, response):
		print(str(self.token(response.token)) + ' = ' + response.remote[0] + ':' + str(response.remote[1]) + ' = ' + response.payload)


class LazyCommunicator(Communicator):

	def __init__(self, delay):
		super(LazyCommunicator, self).__init__()
		self.delay = delay
		self.timestamp = time.time()

	def GET(self, to_node, uri, token, callback):
		tmp = time.time() - self.timestamp - self.delay
		if tmp>=0:
			self.timestamp = time.time()
			reactor.callWhenRunning(self.request, to_node, coap.GET, uri, token, callback)
		else:
			self.timestamp += self.delay
			reactor.callLater(-tmp, self.request, to_node, coap.GET, uri, token, callback)

	def OBSERVE(self, to_node, uri, token, callback):
		tmp = time.time() - self.timestamp - self.delay
		if tmp>=0:
			self.timestamp = time.time()
			reactor.callWhenRunning(self.request, to_node, coap.OBSERVE, uri, token, callback)
		else:
			self.timestamp += self.delay
			reactor.callLater(-tmp, self.request, to_node, coap.OBSERVE, uri, token, callback)

	def POST(self, to_node, uri, payload, token, callback):
		tmp = time.time() - self.timestamp - self.delay
		if tmp>=0:
			self.timestamp = time.time()
			reactor.callWhenRunning(self.request, to_node, coap.POST, uri, token, callback, payload)
		else:
			self.timestamp += self.delay
			reactor.callLater(-tmp, self.request, to_node, coap.POST, uri, token, callback, payload)

	def DELETE(self, to_node, uri, token, callback):
		tmp = time.time() - self.timestamp - self.delay
		if tmp>=0:
			self.timestamp = time.time()
			reactor.callWhenRunning(self.request, to_node, coap.DELETE, uri, token, callback)
		else:
			self.timestamp += self.delay
			reactor.callLater(-tmp, self.request, to_node, coap.DELETE, uri, token, callback)

@deprecated
class RichClient(object):
	class Protocol(CoAP):
		def __init__(self, server=('127.0.0.1', 5684), forward=False):
			CoAP.__init__(self, server, forward)

		@property
		def mid(self):
			return self._currentMID

		@mid.setter
		def mid(self, mid):
			self._currentMID = mid

	def __init__(self, cmd=True):
		self.codes = {v: k for k, v in defines.codes.iteritems()}
		self.codes['OBSERVE'] = 5
		self.forward = not cmd

	def __request(self, to_node, operation, args, kwargs, callback):
		if args[0] is None:
			raise FormatError('URI is missing from CoAP GET request', args[0])
		protocol = self.Protocol((to_node.ip, to_node.port), self.forward)
		if operation == self.codes['GET']:
			function = protocol.get
		elif operation == self.codes['DELETE']:
			function = protocol.delete
		elif operation == self.codes['POST']:
			function = protocol.post
		elif operation == self.codes['OBSERVE']:
			function = protocol.observe
		else:
			raise RequestError('Unsupported request', operation)
		kwargs['Content-Type'] = defines.inv_content_types['application/json']
		kwargs['Accept'] = defines.inv_content_types['application/json']
		protocol.set_operations([(function, args, kwargs, callback)])
		reactor.listenUDP(0, protocol, interface='::')
		try:
			reactor.run()
		except error.ReactorAlreadyRunning:
			pass

	def GET(self, to_node, uri, token, callback, deferred=False):
		if deferred:
			reactor.callWhenRunning(self.__request, to_node, self.codes['GET'], (uri,), {'Token': token} if token else {}, callback)
		else:
			self.__request(to_node, self.codes['GET'], (uri,), {'Token': token} if token else {}, callback)

	def OBSERVE(self, to_node, uri, token, callback, deferred=False):
		if deferred:
			reactor.callWhenRunning(self.__request, to_node, self.codes['OBSERVE'], (uri,), {'Token': token} if token else {}, callback)
		else:
			self.__request(to_node, self.codes['OBSERVE'], (uri,), {'Token': token} if token else {}, callback)

	def DELETE(self, to_node, uri, token, callback, deferred=False):
		if deferred:
			reactor.callWhenRunning(self.__request, to_node, self.codes['DELETE'], (uri,), {'Token': token} if token else {}, callback)
		else:
			self.__request(to_node, self.codes['DELETE'], (uri,), {'Token': token} if token else {}, callback)

	def POST(self, to_node, uri, payload, token, callback, deferred=False):
		if payload is None:
			print("Payload cannot be empty for a POST request")
			raise FormatError('Payload is missing from CoAP POST request', payload)
		if deferred:
			reactor.callWhenRunning(self.__request, to_node, self.codes['POST'], (uri, payload), {'Token': token} if token else {}, callback)
		else:
			self.__request(to_node, self.codes['POST'], (uri, payload), {'Token': token} if token else {}, callback)
