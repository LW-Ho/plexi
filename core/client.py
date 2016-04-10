__author__ = "George Exarchakos"
__version__ = "0.0.9"
__email__ = "g.exarchakos@tue.nl"
__credits__ = ["XYZ"]
__copyright__ = "Copyright 2014, The RICH Project"
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

#from coapthon2 import defines
#from coapthon2.client.coap_protocol import CoAP
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
		self.observers = {}

	def start(self):
		try:
			reactor.run()
		except Exception:
			pass

	def token(self, ticket):
		return self.tickets[ticket] if ticket in self.tickets else None

	def forget(self, token):
		for k,v in self.tickets.items():
			if v == token:
				del self.tickets[k]
				return


	def request(self, to_node, operation, uri, token, callback, payload=None):
		if not payload:
			payload = ''
		tmp = uri.split('?')
		if operation == coap.OBSERVE and to_node in self.observers:
			for req in self.observers[to_node]:
				tmp_path = ""
				first_item = True
				for x in req.opt.uri_path:
					if not first_item:
						tmp_path += "/"
					tmp_path += x
					first_item = False
				if len(tmp) > 0 and tmp_path == tmp[0]:
					return

		request = coap.Message(mtype=coap.CON, code=operation if operation != coap.OBSERVE else coap.GET, token=token, payload=payload)
		request.opt.uri_path = tmp[0].split('/')
		if len(tmp) == 2:
			request.opt.uri_query = tmp[1].split('&')
		request.remote = (to_node.ip, to_node.port)
		#request.opt.accept = coap.media_types_rev['application/json']
		#request.opt.content_format = coap.media_types_rev['application/json']
		protocol = coap.Coap(resource.Endpoint(None))
		ver = netaddr.IPAddress(to_node.ip).version
		if ver == 6:
			reactor.listenUDP(0, protocol, interface='::')
		else:
			reactor.listenUDP(0, protocol)
		if operation == coap.OBSERVE:
			request.opt.observe = 0
			requester = coap.Requester(protocol, request, observeCallback=callback, block1Callback=None, block2Callback=None, observeCallbackArgs=None, block1CallbackArgs=None, block2CallbackArgs=None, observeCallbackKeywords=None, block1CallbackKeywords=None, block2CallbackKeywords=None)
			if to_node not in self.observers:
				self.observers[to_node] = [request]
			else:
				self.observers[to_node] += [request]
		else:
			requester = coap.Requester(protocol, request, observeCallback=None, block1Callback=None, block2Callback=None, observeCallbackArgs=None, block1CallbackArgs=None, block2CallbackArgs=None, observeCallbackKeywords=None, block1CallbackKeywords=None, block2CallbackKeywords=None)
		if callback is not None:
			requester.deferred.addCallback(callback)
		self.tickets[requester.app_request.token] = token
		self.start()

	def GET(self, to_node, uri, token, callback):
		reactor.callWhenRunning(self.request, to_node, coap.GET, uri, token, callback)

	def OBSERVE(self, to_node, uri, token, callback):
		reactor.callWhenRunning(self.request, to_node, coap.OBSERVE, uri, token, callback)

	def CANCEL_OBSERVE(self, to_node, uri, token, callback):
		protocol = coap.Coap(resource.Endpoint(None))
		ver = netaddr.IPAddress(to_node.ip).version
		if ver == 6:
			reactor.listenUDP(0, protocol, interface='::')
		else:
			reactor.listenUDP(0, protocol)
		tmp = uri.split('?')
		for req in self.observers[to_node]:
			tmp_path = ""
			first_item = True
			for x in req.opt.uri_path:
				if not first_item:
					tmp_path += "/"
				tmp_path += x
				first_item = False
			if len(tmp) > 0 and tmp_path == tmp[0]:
				req.opt.observe = 1
				requester = coap.Requester(protocol, req, observeCallback=None, block1Callback=None, block2Callback=None, observeCallbackArgs=None, block1CallbackArgs=None, block2CallbackArgs=None, observeCallbackKeywords=None, block1CallbackKeywords=None, block2CallbackKeywords=None)
				if callback is not None:
					requester.deferred.addCallback(callback)
				self.forget(token)

	def POST(self, to_node, uri, payload, token, callback):
		reactor.callWhenRunning(self.request, to_node, coap.POST, uri, token, callback, payload)

	def DELETE(self, to_node, uri, token, callback):
		reactor.callWhenRunning(self.request, to_node, coap.GET, uri, token, callback)

	def test_callable(self, response):
		print(str(self.token(response.token)) + ' = ' + response.remote[0] + ':' + str(response.remote[1]) + ' = ' + response.content)


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
