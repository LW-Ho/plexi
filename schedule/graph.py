import networkx as nx
from gephier import GephiClient
from util.warn import deprecated


class DoDAG(object):
	def __init__(self, name, root, visualize=False):
		self.graph = nx.Graph(name=name)
		self.root = root
		self.graph.add_node(root)
		self.visualize = visualize
		if self.visualize:
			try:
				self.visualizer = GephiClient('http://localhost:8081/richnet', autoflush=True)
				self.visualizer.clean()
			except:
				self.visualize = False

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
				self.visualizer.add_node(str(node_id), {"size":20, 'r':1.0, 'g':0.0, 'b':0.0, 'x':1, 'y':2})
			return True
		return False


	def attach_child(self, child_id, parent_id):
		#if child_id in self.graph.nodes() and parent_id in self.graph.nodes():
		for neighbor in self.graph.neighbors(child_id):
			if 'parent' in self.graph[child_id][neighbor]:
				if self.graph[child_id][neighbor]['parent'] != parent_id:
					self.graph.remove_edge(child_id, neighbor)
					if self.visualize:
						self.visualizer.delete_edge(str(child_id)+'-'+str(parent_id))
				else:
					return False
		self.graph.add_edge(child_id, parent_id, parent=parent_id, child=child_id)
		if self.visualize:
			self.visualizer.add_edge(str(child_id)+'-'+str(parent_id),str(child_id), str(parent_id), False)
		return True
		#return False

	@deprecated
	def attach_parent(self, parent_id, child_id):
		self.attach_child(child_id, parent_id)

	def detach_node(self, node_id):
		if node_id in self.graph.nodes():
			self.graph.remove_node(node_id)
			return True
		return False
