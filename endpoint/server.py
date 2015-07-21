__author__ = "George Exarchakos"
__version__ = "0.0.9"
__email__ = "g.exarchakos@tue.nl"
__credits__ = ["XYZ"]
__copyright__ = "Copyright 2014, The RICH Project"
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from coapthon2.server.coap_protocol import CoAP
from coapthon2.resources.resource import Resource
from resource import rpl, sixtop
import networkx
from util import terms


class LBRServer(CoAP):
	def __init__(self, graph, node_id):
		CoAP.__init__(self)
		self.add_resource('rpl/', Resource('RPL'))
		if isinstance(graph, networkx.Graph):
			self.add_resource('rpl/nl/', rpl.NodeList(graph))
			self.add_resource('rpl/c/', rpl.ChildrenList('rpl.children', graph, node_id, []))
			self.add_resource('6t/6/sf/', sixtop.SlotframeList('6top.slotframes'))
		else:
			raise TypeError('Server needs a networkx.Graph to retrieve data')


class NodeServer(CoAP):
	def __init__(self, graph, node_id):
		CoAP.__init__(self)
		self.add_resource(terms.uri['RPL'], Resource('rpl'))
		self.add_resource(terms.uri['6TP'], Resource('6tisch'))
		self.add_resource(terms.uri['6TP_6'], Resource('6top'))
		if isinstance(graph, networkx.Graph):
			#self.add_resource('rpl/p/', rpl.ParentList('rpl.parents', graph, node_id, parent_id))
			self.add_resource(terms.uri['RPL_NL'], rpl.NodeList(graph))
			children = [n for n in graph.neighbors(node_id) if 'child' in graph[node_id][n] and graph[node_id][n]['child'] != node_id]
			self.add_resource(terms.uri['RPL_OL'], rpl.ChildrenList('rpl.children', graph, node_id, children))
			self.add_resource(terms.uri['6TP_SF'], sixtop.SlotframeList('6top.slotframes'))
			self.add_resource(terms.uri['6TP_CL'], sixtop.CellList('6top.cells'))
		else:
			raise TypeError('Server needs a networkx.Graph to retrieve data')