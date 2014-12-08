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
from util import terms


class DoDAG(object):
	def __init__(self, name, root, visualize=False):
		self.graph = nx.Graph(name=name)
		self.root = root
		self.visualize = visualize
		if self.visualize:
			try:
				self.visualizer = GephiClient('http://'+visualize+'/richnet', autoflush=True)
				self.visualizer.clean()
				self.root_attrs = {'size':120, 'r':1.0, 'g':0.0, 'b':0.0}
				self.router_attrs = {'size':120, 'r':0.0, 'g':1.0, 'b':0.0}
				self.leaf_attrs = {'size':120, 'r':0.0, 'g':0.0, 'b':1.0}
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
					tmp_attrs = self.root_attrs
					tmp_attrs['label'] = node_id.stripdown()
					self.visualizer.add_node(str(node_id), **self.root_attrs)
				else:
					tmp_attrs = self.leaf_attrs
					tmp_attrs['label'] = node_id.stripdown()
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
						tmp_attrs = {'parent':'null'}
						self.visualizer.change_node(str(child_id), **tmp_attrs)
				elif self.graph[child_id][neighbor]['parent'] == child_id and neighbor == parent_id:
					self.graph.remove_edge(child_id, neighbor)
					if self.visualize:
						self.visualizer.delete_edge(str(neighbor)+'-'+str(child_id))
						self._visual_motion(child_id)
						self._visual_motion(neighbor)
						tmp_attrs = {'parent':'null'}
						self.visualizer.change_node(str(neighbor), *tmp_attrs)
				elif self.graph[child_id][neighbor]['parent'] == parent_id:
					return False
		self.graph.add_edge(child_id, parent_id, parent=parent_id, child=child_id)
		if self.visualize:
			self.visualizer.add_edge(str(child_id)+'-'+str(parent_id),str(child_id), str(parent_id), False)
			tmp_attrs = {'parent':str(parent_id)}
			self.visualizer.change_node(str(child_id), **tmp_attrs)
			promote = True
			for k,v in self.graph[parent_id].items():
				if 'parent' in v and v['parent'] == parent_id and k != child_id:
					promote = False
					break
			if promote and parent_id != self.root:
				self.visualizer.change_node(str(parent_id), **self.router_attrs)
		return True

	def update_link(self, sender, receiver, metric, value):
		if sender in self.graph.nodes():
			if metric in terms.keys.keys() and receiver in self.graph[sender]:
				if 'parent' in self.graph[sender][receiver]:
					if self.graph[sender][receiver]['parent']==receiver:
						if metric=='SLT' and value=='++':
							if 'UP-'+terms.keys[metric] not in self.graph[sender][receiver]:
								self.graph[sender][receiver]['UP-'+terms.keys[metric]] = 0
							self.graph[sender][receiver]['UP-'+terms.keys[metric]] = self.graph[sender][receiver]['UP-'+terms.keys[metric]]+1
						else:
							self.graph[sender][receiver]['UP-'+terms.keys[metric]] = value
						tmp_attrs = {'UP-'+terms.keys[metric]: self.graph[sender][receiver]['UP-'+terms.keys[metric]]}
						self.visualizer.change_edge(str(sender)+'-'+str(receiver), **tmp_attrs)
					else:
						if metric=='SLT' and value=='++':
							if 'DOWN-'+terms.keys[metric] not in self.graph[sender][receiver]:
								self.graph[sender][receiver]['DOWN-'+terms.keys[metric]] = 0
							self.graph[sender][receiver]['DOWN-'+terms.keys[metric]] = self.graph[sender][receiver]['DOWN-'+terms.keys[metric]] + 1
						else:
							self.graph[sender][receiver]['DOWN-'+terms.keys[metric]] = value
						tmp_attrs = {'DOWN-'+terms.keys[metric]: self.graph[sender][receiver]['DOWN-'+terms.keys[metric]]}
					self.visualizer.change_edge(str(receiver)+'-'+str(sender), **tmp_attrs)

	def update_node(self, node_id, metric, value):
		if node_id in self.graph.nodes():
			if metric in terms.keys.keys():
				if metric == 'SLT' and value == '++':
					if 'BC-'+terms.keys[metric] not in self.graph[node_id]:
						self.graph[node_id]['BC-'+terms.keys[metric]] = 0
					self.graph[node_id]['BC-'+terms.keys[metric]] = self.graph[node_id]['BC-'+terms.keys[metric]]+1
				else:
					self.graph[node_id]['BC-'+terms.keys[metric]] = value
				tmp_attrs = {'BC-'+terms.keys[metric]: self.graph[node_id]['BC-'+terms.keys[metric]]}
				self.visualizer.change_node(str(node_id), **tmp_attrs)

	@deprecated
	def attach_parent(self, parent_id, child_id):
		self.attach_child(child_id, parent_id)

	def detach_node(self, node_id):
		if node_id in self.graph.nodes():
			self.graph.remove_node(node_id)
			return True
		return False
