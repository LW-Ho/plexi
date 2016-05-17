__author__ = "George Exarchakos"
__version__ = "0.0.8"
__email__ = "g.exarchakos@tue.nl"
__credits__ = ["Michael Chermside"]
__copyright__ = "Copyright 2014, The RICH Project"
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

import os
import sys
import ipaddress

class NodeID(object):
	prefix = "aaaa"
	def __init__(self, ip="0:0:0:0", port=5684):
		if isinstance(ip, unicode):
			ip = str(ip.encode('utf-8'))
		if isinstance(ip, str):
			if ip[0] == '[':
				self.ip, self.port = ip.split('[')[1].split(']')
				self.port = self.port.split(':')[1]
			elif isinstance(port, int):
				self.ip = ip
				self.port = port
			else:
				raise TypeError('IP address is a string value and the port is an integer')
			# if self.ip.count(':') == 3:
			# 	self.ip = NodeID.prefix + '::' + self.ip
			# self.eui_64_ip = ''
			if self.prefix in self.ip:
				self.ip = self.ip.split(u'::')[-1]
			self.eui_64_ip = str(ipaddress.ip_address(u'::' + self.ip))
			self.ip = self.prefix + str(ipaddress.ip_address(u'::' + self.ip))
			# parts = self.ip.split(':')
			# parts = parts[len(parts)-4 : len(parts)]
			# self.eui_64_ip += parts[0] + ':' + parts[1] + ':' + parts[2] + ':' + parts[3]
			self.port = port
		else:
			raise TypeError('IP address is a string value and the port is an integer')

	def __eq__(self, other):
		try:
			return other is not None and self.ip == other.ip and self.port == other.port
		except Exception:
			return other is not None and self.ip == other

	def __ne__(self, other):
		try:
			return other is None or self.ip != other.ip or self.port != other.port
		except Exception:
			return other is None and self.ip != other


	def __repr__(self):
		return self.__str__()

	def __str__(self):
		return '[' + str(self.ip) + ']:' + str(self.port)

	def __hash__(self):
		return hash(self.__str__())

	# def stripdown(self):
	# 	parts = self.eui_64_ip.split(':')
	# 	parts = parts[len(parts)-2 : len(parts)]
	# 	return parts[0] + ':' + parts[1]

	def is_broadcast(self):
		return self.prefix+'fff:ffff:ff:ffff' == self.ip

BROADCASTID = NodeID(u"fff:ffff:ff:ffff")
