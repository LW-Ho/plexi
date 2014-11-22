__author__ = "George Exarchakos, Dimitris Sarakiotis, Ilker Oztelcan"
__email__ = "g.exarchakos@tue.nl, d.sarakiotis@tue.nl, i.oztelcan@tue.nl"
__version__ = "0.0.21"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

import networkx as nx
from gephier import GephiClient
from util.warn import deprecated


class DoDAG(object):
	def __init__(self, name, root, visualize=False):
		self.graph = nx.Graph(name=name)
		self.root = root
		self.visualize = visualize
		if self.visualize:
			try:
				self.visualizer = GephiClient('http://'+visualize+'/richnet', autoflush=True)
				self.visualizer.clean()
				self.root_attrs = {"size":40, 'r':1.0, 'g':0.0, 'b':0.0}
				self.router_attrs = {"size":30, 'r':0.0, 'g':1.0, 'b':0.0}
				self.leaf_attrs = {"size":20, 'r':0.0, 'g':0.0, 'b':1.0}
			except:
				self.visualize = False
		self.attach_node(root)

	def get_parent(self, child_id):
		if child_id in self.graph.nodes():
			for neighbor in self.graph.neighbors(child_id):
				if 'parent' in self.graph[child_id][neighbor]:
					return neighbor
		return None

	def attach_node(self, node_id):
		if node_id not in self.graph.nodes():
			self.graph.add_node(node_id)
			if self.visualize:
				if node_id == self.root:
					self.visualizer.add_node(str(node_id), **self.root_attrs)
				else:
					self.visualizer.add_node(str(node_id), **self.leaf_attrs)
			return True
		return False

	def _visual_motion(self, node):
		demote = True
		for k,v in self.graph[node].items():
			if 'parent' in v and v['parent'] == node:
				demote = False
				break
		if demote and node != self.root:
			self.visualizer.change_node(str(node), **self.leaf_attrs)

	def attach_child(self, child_id, parent_id):
		if child_id == self.root:
			return False
		if child_id not in self.graph.nodes():
			self.attach_node(child_id)
		if parent_id not in self.graph.nodes():
			self.attach_node(parent_id)
		for neighbor in self.graph.neighbors(child_id):
			if 'parent' in self.graph[child_id][neighbor]:
				if self.graph[child_id][neighbor]['parent'] != parent_id and self.graph[child_id][neighbor]['parent'] != child_id:
					self.graph.remove_edge(child_id, neighbor)
					if self.visualize:
						self.visualizer.delete_edge(str(child_id)+'-'+str(neighbor))
						self._visual_motion(child_id)
						self._visual_motion(neighbor)
				elif self.graph[child_id][neighbor]['parent'] == child_id and neighbor == parent_id:
					self.graph.remove_edge(child_id, neighbor)
					if self.visualize:
						self.visualizer.delete_edge(str(neighbor)+'-'+str(child_id))
						self._visual_motion(child_id)
						self._visual_motion(neighbor)
				elif self.graph[child_id][neighbor]['parent'] == parent_id:
					return False
		self.graph.add_edge(child_id, parent_id, parent=parent_id, child=child_id)
		if self.visualize:
			self.visualizer.add_edge(str(child_id)+'-'+str(parent_id),str(child_id), str(parent_id), False)
			promote = True
			for k,v in self.graph[parent_id].items():
				if 'parent' in v and v['parent'] == parent_id and k != child_id:
					promote = False
					break
			if promote and parent_id != self.root:
				self.visualizer.change_node(str(parent_id), **self.router_attrs)
		return True

	@deprecated
	def attach_parent(self, parent_id, child_id):
		self.attach_child(child_id, parent_id)

	def detach_node(self, node_id):
		if node_id in self.graph.nodes():
			self.graph.remove_node(node_id)
			return True
		return False
