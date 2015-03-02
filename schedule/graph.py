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
from twisted.internet import reactor
import urllib2, logging

logg = logging.getLogger('RiSCHER')
logg.setLevel(logging.DEBUG)


class DoDAG(object):
	def __init__(self, name, root, visualize=False):
		self.graph = nx.Graph(name=name)
		self.root = root
		self.visualize = visualize
		self.root_attrs = {'r':1.0, 'g':0.0, 'b':0.0}
		self.router_attrs = {'r':0.0, 'g':1.0, 'b':0.0}
		self.leaf_attrs = {'r':0.0, 'g':0.0, 'b':1.0}
		self.visualizer = None
		if self.visualize:
			self.flush_to_visualizer(self.visualize)
		self.attach_node(root)

	# returns the parent_id of the inputted child_id
	def get_parent(self, child_id):
		if child_id in self.graph.nodes():
			for neighbor in self.graph.neighbors(child_id):
				if 'parent' in self.graph.edge[child_id][neighbor] and self.graph.edge[child_id][neighbor]['parent'] == neighbor:
					return neighbor
		return None

	# adds a node to the DoDAG graph and to the vizualized network graph
	def attach_node(self, node_id):
		if node_id not in self.graph.nodes():
			self.graph.add_node(node_id)    # adds the node with node_id to the locally stored graph
			try:
				if self.visualize and self.visualizer is not None:
					if node_id == self.root:
						tmp_attrs = self.root_attrs
						tmp_attrs['label'] = node_id.stripdown()
						self.visualizer.add_node(str(node_id), **self.root_attrs)
					else:
						tmp_attrs = self.leaf_attrs
						tmp_attrs['label'] = node_id.stripdown()
						self.visualizer.add_node(str(node_id), **self.leaf_attrs)
			except:
				self.visualizer = None
				if self.visualize:
					logg.warning('Visualizer - '+self.visualize+' - is unreachable, retrying in 10sec ...')
					reactor.callLater(10, self.flush_to_visualizer, self.visualize)
			return True
		return False

	def _visual_motion(self, node):
		tmp_attrs = {}
		children = 0
		parent = None
		for k,v in self.graph.edge[node].items():
			if 'parent' in v and v['parent'] == node:
				children += 1
			elif 'child' in v and v['child'] == node:
				parent = v['parent']
		if parent is None:
			tmp_attrs = self.root_attrs
		elif children==0 and parent is not None:
			tmp_attrs = self.leaf_attrs
		elif children>0 and parent is not None:
			tmp_attrs = self.router_attrs
		self.visualizer.change_node(str(node), **tmp_attrs)

	# creates a link (child-parent link) to the locally kept DoDAG graph
	def attach_child(self, child_id, parent_id):
		if child_id == self.root:
			return False
		if child_id not in self.graph.nodes():
			self.attach_node(child_id)
		if parent_id not in self.graph.nodes():
			self.attach_node(parent_id)
		for neighbor in self.graph.neighbors(child_id):
			if 'parent' in self.graph.edge[child_id][neighbor]:
				if self.graph.edge[child_id][neighbor]['parent'] != parent_id and self.graph.edge[child_id][neighbor]['parent'] != child_id:
					self.graph.remove_edge(child_id, neighbor)
					try:
						if self.visualize and self.visualizer is not None:
							self.visualizer.delete_edge(str(child_id)+'-'+str(neighbor))
							self._visual_motion(child_id)
							self._visual_motion(neighbor)
					except:
						self.visualizer = None
						if self.visualize:
							logg.warning('Visualizer - '+self.visualize+' - is unreachable, retrying in 10sec ...')
							reactor.callLater(10, self.flush_to_visualizer, self.visualize)
				elif self.graph.edge[child_id][neighbor]['parent'] == child_id and neighbor == parent_id:
					self.graph.remove_edge(child_id, neighbor)
					try:
						if self.visualize and self.visualizer is not None:
							self.visualizer.delete_edge(str(neighbor)+'-'+str(child_id))
							self._visual_motion(child_id)
							self._visual_motion(neighbor)
					except:
						self.visualizer = None
						if self.visualize:
							logg.warning('Visualizer - '+self.visualize+' - is unreachable, retrying in 10sec ...')
							reactor.callLater(10, self.flush_to_visualizer, self.visualize)
				elif self.graph.edge[child_id][neighbor]['parent'] == parent_id:
					return False
		self.graph.add_edge(child_id, parent_id, parent=parent_id, child=child_id)
		try:
			if self.visualize and self.visualizer is not None:
				self.visualizer.add_edge(str(child_id)+'-'+str(parent_id), str(child_id), str(parent_id), False)
				self._visual_motion(child_id)
				self._visual_motion(parent_id)
		except:
			self.visualizer = None
			if self.visualize:
				logg.warning('Visualizer - '+self.visualize+' - is unreachable, retrying in 10sec ...')
				reactor.callLater(10, self.flush_to_visualizer, self.visualize)
		return True

	# updates the link's statistics/metrics info for the visualizer
	def update_link(self, node, endpoint, metric, value):
		if metric in terms.keys.keys() and self.graph.has_edge(node, endpoint):
			if "statistics" not in self.graph.edge[node][endpoint]:
				self.graph.edge[node][endpoint]["statistics"] = {}
			if node not in self.graph.edge[node][endpoint]["statistics"]:
				self.graph.edge[node][endpoint]["statistics"][node] = {}
			if value == '++':
				if terms.keys[metric] not in self.graph.edge[node][endpoint]['statistics'][node]:
					self.graph.edge[node][endpoint]['statistics'][node][terms.keys[metric]] = 0
				self.graph.edge[node][endpoint]['statistics'][node][terms.keys[metric]] += 1
			elif value == '--':
				if terms.keys[metric] not in self.graph.edge.edge[node][endpoint]['statistics'][node]:
					self.graph.edge[node][endpoint]['statistics'][node][terms.keys[metric]] = 0
				self.graph.edge[node][endpoint]['statistics'][node][terms.keys[metric]] -= 1
			else:
				self.graph.edge[node][endpoint]['statistics'][node][terms.keys[metric]] = value
			try:
				if self.visualize and self.visualizer is not None:
					direction = 'P-'
					if 'child' in self.graph.edge[node][endpoint] and self.graph.edge[node][endpoint]['child']==node:
						direction = 'C-'
					tmp_attrs = {direction+terms.keys[metric]: self.graph.edge[node][endpoint]['statistics'][node][terms.keys[metric]]}
					id = str(self.graph.edge[node][endpoint]['child']) + '-' + str(self.graph.edge[node][endpoint]['parent'])
					self.visualizer.change_edge(id, **tmp_attrs)
			except:
				self.visualizer = None
				if self.visualize:
					logg.warning('Visualizer - '+self.visualize+' - is unreachable, retrying in 10sec ...')
					reactor.callLater(10, self.flush_to_visualizer, self.visualize)

	# updates node's info for the visualizer
	def update_node(self, node_id, metric, value):
		if node_id in self.graph.nodes():
			if metric in terms.keys.keys():
				if metric == 'SLT' and value == '++':
					if 'BC-'+terms.keys[metric] not in self.graph.node[node_id]:
						self.graph.node[node_id]['BC-'+terms.keys[metric]] = 0
					self.graph.node[node_id]['BC-'+terms.keys[metric]] = self.graph.node[node_id]['BC-'+terms.keys[metric]]+1
				else:
					self.graph.node[node_id]['BC-'+terms.keys[metric]] = value
				try:
					if self.visualize and self.visualizer is not None:
						tmp_attrs = {'BC-'+terms.keys[metric]: self.graph.node[node_id]['BC-'+terms.keys[metric]]}
						self.visualizer.change_node(str(node_id), **tmp_attrs)
				except:
					self.visualizer = None
					if self.visualize:
						logg.warning('Visualizer - '+self.visualize+' - is unreachable, retrying in 10sec ...')
						reactor.callLater(10, self.flush_to_visualizer, self.visualize)

	# removes a node from the locally kept DoDAG
	def detach_node(self, node_id):
		if node_id in self.graph.nodes():
			self.graph.remove_node(node_id)
			return True
		return False

	def flush_to_visualizer(self, visualize):
		try:
			self.visualizer = GephiClient('http://'+visualize, autoflush=True)
			logg.warning('Visualizer - ' + self.visualize + ' - is now reachable ... ')
			self.visualizer.clean()
			nodes = [n for n in self.graph.nodes_iter(data=True)]
			for no in nodes:
				tmp_attrs = no[1]
				self.visualizer.add_node(str(no[0]), **tmp_attrs)
			edges = [e for e in self.graph.edges_iter(data=True)]
			for ed in edges:
				if 'child' in ed[2] and 'parent' in ed[2]:
					child = ed[2]['child']
					parent = ed[2]['parent']
					tmp_attrs = {}
					if 'statistics' in ed[2]:
						for (k,v) in ed[2]['statistics'].items():
							direction = 'P-'
							if ed[2]['child'] == k:
								direction = 'C-'
							for (metric,value) in v.items():
								tmp_attrs[direction+metric] = value
					self.visualizer.add_edge(str(child)+'-'+str(parent),str(child), str(parent), False, **tmp_attrs)
					self._visual_motion(child)
					self._visual_motion(parent)
		except:
			logg.warning('Visualizer - '+visualize+' - is unreachable, retrying in 10sec ...')
			reactor.callLater(10, self.flush_to_visualizer, visualize)