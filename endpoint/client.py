#!/bin/python

from coapthon2 import defines
from coapthon2.client.coap_protocol import CoAP, HelperClient
from util.exception import FormatError, RequestError
from twisted.internet import reactor, error


class RichClient(object):
	class Protocol(CoAP):
		def __init__(self, server=('127.0.0.1', 5683), forward=False):
			CoAP.__init__(self, server, forward)

		@property
		def starting_mid(self):
			return self._currentMID

		@starting_mid.setter
		def starting_mid(self, mid):
			self._currentMID = mid

	def __init__(self, cmd=True):
		self.codes = {v: k for k, v in defines.codes.iteritems()}
		self.codes['OBSERVE'] = 5
		self.clients = []
		self.at_least_one_observer = False
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
			self.at_least_one_observer = True
		else:
			raise RequestError('Unsupported request', operation)
		kwargs['Content-Type'] = defines.inv_content_types['application/json']
		kwargs['Accept'] = defines.inv_content_types['application/json']
		protocol.set_operations([(function, args, kwargs, callback)])
		reactor.listenUDP(0, protocol)
		try:
			reactor.run()
		except error.ReactorAlreadyRunning:
			print 'reactor: business as usual'

	def GET(self, to_node, uri, callback):
		self.__request(to_node, self.codes['GET'], (uri,), {}, callback)

	def OBSERVE(self, to_node, uri, token, callback):
		if token is None:
			print "Token cannot be empty for an OBSERVE request"
			raise FormatError('Token is missing from CoAP OBSERVE request', token)
		return self.__request(to_node, self.codes['OBSERVE'], (uri,), {'Token': token}, callback)

	def DELETE(self, to_node, uri, callback):
		return self.__request(to_node, self.codes['DELETE'], (uri,), {}, callback)

	def POST(self, to_node, uri, payload, callback):
		if payload is None:
			print "Payload cannot be empty for a POST request"
			raise FormatError('Payload is missing from CoAP POST request', payload)
		return self.__request(to_node, self.codes['POST'], (uri, payload), {}, callback)
