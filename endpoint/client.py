#!/bin/python

from coapthon2 import defines
from coapthon2.client.coap_protocol import CoAP
from util.exception import FormatError, RequestError
from twisted.internet import reactor, error


class RichClient(object):
	class Protocol(CoAP):
		def __init__(self, server=('127.0.0.1', 5683), forward=False):
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
		reactor.listenUDP(0, protocol)# TODO , interface='::')
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