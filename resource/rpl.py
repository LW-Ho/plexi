__author__ = "George Exarchakos"
__version__ = "0.0.8"
__email__ = "g.exarchakos@tue.nl"
__credits__ = ["Michael Chermside"]
__copyright__ = "Copyright 2014, The RICH Project"
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from coapthon2.resources.resource import Resource
from coapthon2 import defines
import networkx
import json


class NodeID(object):
	def __init__(self, ip, port=5684):
		if isinstance(ip, str):
			if ip[0] == '[':
				self.ip, self.port = ip.split('[')[1].split(']')
				self.port = self.port.split(':')[1]
			elif isinstance(port, int):
				self.ip = ip
				self.port = port
			else:
				raise TypeError('IP address is a string value and the port is an integer')
			if self.ip.count(':') == 3:
				self.ip = 'aaaa::' + self.ip  # TODO: bad dirty fix. Fix properly
			self.eui_64_ip = ''
			parts = self.ip.split(':')
			parts = parts[len(parts)-4 : len(parts)]
			self.eui_64_ip += parts[0] + ':' + parts[1] + ':' + parts[2] + ':' + parts[3]
		else:
			raise TypeError('IP address is a string value and the port is an integer')

	def __eq__(self, other):
		return self.ip == other.ip and self.port == other.port

	def __ne__(self, other):
		return self.ip != other.ip or self.port != other.port

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		return '[' + str(self.ip) + ']:' + str(self.port)

	def __hash__(self):
		return hash(self.__str__())

	def stripdown(self):
		parts = self.eui_64_ip.split(':')
		parts = parts[len(parts)-2 : len(parts)]
		return parts[0] + ':' + parts[1]


class NodeList(Resource):
	def __init__(self, graph):
		super(NodeList, self).__init__(name='NodeList', visible=True, observable=True, allow_children=False)
		self.add_content_type('application/json')
		if isinstance(graph, networkx.Graph):
			self.graph = graph
			self.payload = {'application/json': [(n.ip, n.port) for n in self.graph.nodes()]}
		else:
			raise TypeError('networkx undirected graph was expected')

	def render_GET(self, request, query=None):
		# return nothing and a 4.04 Not Found error will be sent back
		# return a payload and a 2.05 Content will be sent back
		try:
			if not query:
				self.payload = {'application/json': [(n.ip, n.port) for n in self.graph.nodes()]}
				return {'Payload': self.payload}
		except:
			pass


class ParentList(Resource):
	def __init__(self, name, graph=None, node_id=None, parent_id=None):
		if not isinstance(name, ParentList):
			super(ParentList, self).__init__(name=name, visible=True, observable=True, allow_children=False)
			if isinstance(graph, networkx.Graph) and isinstance(node_id, NodeID) and isinstance(parent_id, NodeID):
				self.graph = graph
				self.node_id = node_id
				self.add_content_type('application/json')
				self.payload = {'application/json': [(parent_id.ip, parent_id.port)]}
				self.set_parent(parent_id)
			else:
				raise TypeError('networkx undirected graph was expected, a NodeID node and a NodeID parent')
		else:
			super(ParentList, self).__init__(name)
			self.graph = name.graph
			self.node_id = name.node_id

	def render_GET(self, request, query=None):
		# return nothing and a 4.04 Not Found error will be sent back
		# return a payload and a 2.05 Content will be sent back
		return {'Payload': self.payload}

	def render_POST(self, request, payload=None, query=None):
		# return {Payload:<P>,Callback:<C>,Resource:None,Location-Query:<LQ>}
		# return {Payload:-1,Callback:<C>,Resource:None,Location-Query:<LQ>} for METHOD_NOT_ALLOWED
		# return {Payload:None,Callback:<C>,Resource:None,Location-Query:<LQ>} for INTERNAL_SERVER_ERROR
		tmp_dict = json.loads(str(payload))
		parent_id = NodeID(str(tmp_dict[0][0]), tmp_dict[0][1])
		self.payload = {'application/json': [(parent_id.ip, parent_id.port)]}
		self.set_parent(parent_id)
		return {'Payload': self.payload, 'Location-Query': query}

	def set_parent(self, parent_id):
		if self.node_id in self.graph.nodes() and parent_id in self.graph.nodes():
			for neighbor in self.graph.neighbors(self.node_id):
				if 'parent' in self.graph[self.node_id][neighbor]:
					if self.graph[self.node_id][neighbor]['parent'] != parent_id:
						del self.graph[self.node_id][neighbor]['parent']
						break
					else:
						return
			self.graph.add_edge(self.node_id, parent_id, parent=parent_id)


class ChildrenList(Resource):
	def __init__(self, name, graph=None, node_id=None, children_ids=None):
		if not isinstance(name, ChildrenList):
			super(ChildrenList, self).__init__(name=name, visible=True, observable=True, allow_children=False)
			if isinstance(graph, networkx.Graph) and isinstance(node_id, NodeID):
				for child in children_ids:
					if not isinstance(child, NodeID):
						raise TypeError('children_ids should be of type NodeID')
				self.graph = graph
				self.node_id = node_id
				self.add_content_type('application/json')
				self.set_children(children_ids)
				self.payload = {
					'application/json': []}  # (i.ip, i.port) for i in self.graph.neighbors(self.node_id) if self.graph[self.node_id][i]['child'] != self.node_id]}
			else:
				raise TypeError('networkx undirected graph was expected, a NodeID node and a NodeID parent')
		else:
			super(ChildrenList, self).__init__(name)
			self.graph = name.graph
			self.node_id = name.node_id

	def render_GET(self, request, query=None):
		# return nothing and a 4.04 Not Found error will be sent back
		# return a payload and a 2.05 Content will be sent back
		self.payload = {'application/json': [(i.ip, i.port) for i in self.graph.neighbors(self.node_id) if
												'child' in self.graph[self.node_id][i] and self.graph[self.node_id][i][
													'child'] != self.node_id]}
		return {'Payload': self.payload}

	def render_POST(self, request, payload=None, query=None):
		# return {Payload:<P>,Callback:<C>,Resource:None,Location-Query:<LQ>}
		# return {Payload:-1,Callback:<C>,Resource:None,Location-Query:<LQ>} for METHOD_NOT_ALLOWED
		# return {Payload:None,Callback:<C>,Resource:None,Location-Query:<LQ>} for INTERNAL_SERVER_ERROR
		children_ids = []
		tmp_dict = json.loads(str(payload))
		for child in tmp_dict[0]:
			children_ids.append(NodeID(str(tmp_dict[0][0]), tmp_dict[0][1]))
		self.payload = {'application/json': [(i.ip, i.port) for i in children_ids if
		                                     self.graph[self.node_id][i]['child'] != self.node_id]}
		self.set_children(children_ids)
		return {'Payload': self.payload, 'Location-Query': query}

	def set_children(self, children_ids):
		if self.node_id in self.graph.nodes():
			for child in children_ids:
				if child in self.graph.nodes():
					for neighbor in self.graph.neighbors(child):
						if 'parent' in self.graph[child][neighbor]:
							if self.graph[child][neighbor]['parent'] != self.node_id:
								del self.graph[child][neighbor]['parent']
								del self.graph[child][neighbor]['child']
								break
							else:
								return
					self.graph.add_edge(self.node_id, child, parent=self.node_id, child=child)