from coapthon2.server.coap_protocol import CoAP
from coapthon2.resources.resource import Resource
from resource import rpl, sixtop
import networkx

class ResourceContainer(object):
	def __init__(self):
		self.frames = 0

	def newFrameID(self, size):
		return ++self.frames


class LBRServer(CoAP):
	def __init__(self, graph):
		CoAP.__init__(self)
		self.add_resource('rpl/', Resource('RPL'))
		if isinstance(graph, networkx.Graph):
			self.add_resource('rpl/node/', rpl.NodeList(graph))
		else:
			raise TypeError('Server needs a networkx.Graph to retrieve data')


class NodeServer(CoAP):
	def __init__(self, graph, node_id, parent_id):
		CoAP.__init__(self)
		self.add_resource('rpl/', Resource('RPL'))
		self.add_resource('6t/', Resource('6tisch'))
		self.add_resource('6t/6/', Resource('6top'))
		if isinstance(graph, networkx.Graph):
			self.add_resource('rpl/p/', rpl.ParentList('rpl.parents', graph, node_id, parent_id))
			self.add_resource('rpl/c/', rpl.ChildrenList('rpl.children', graph, node_id, []))
			self.add_resource('6t/6/sf/', sixtop.SlotframeList('6top.slotframes', 101))
		else:
			raise TypeError('Server needs a networkx.Graph to retrieve data')