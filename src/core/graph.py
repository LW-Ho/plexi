__author__ = "George Exarchakos, Dimitris Sarakiotis, Ilker Oztelcan, Frank Boerman"
__email__ = "g.exarchakos@tue.nl, d.sarakiotis@tue.nl, i.oztelcan@tue.nl, f.j.l.boerman@student.tue.nl"
__version__ = "0.0.21"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

import networkx as nx
from util import terms
from twisted.internet import reactor
import urllib2, logging
# import matplotlib.pyplot as plt
from subprocess import call

logg = logging.getLogger('RiSCHER')
logg.setLevel(logging.DEBUG)


class DoDAG(object):
	"""
	Keep track of the dodag tree of the network.

	This uses a networkx graph in the background and can dump it to file with graphviz package


	"""
	def __init__(self, name, root, visualize=False):
		"""
		create the networkx graph and setup the attributes and root node

		:param name: name of the graph
		:param root: ID of the border router
		:param visualize: the gephi visualizer NOT USED ANYMORE
		:return:
		"""
		self.graph = nx.Graph(name=name)
		self.root = root
		self.root_attrs = {'r':1.0, 'g':0.0, 'b':0.0}
		self.router_attrs = {'r':0.0, 'g':1.0, 'b':0.0}
		self.leaf_attrs = {'r':0.0, 'g':0.0, 'b':1.0}
		self.attach_node(root)

	#CHANGED BY FRANK
	#draws the graph using matplotlib
	# def draw_graph_old(self):
	# 	# layout = nx.spring_layout(self.graph)
	# 	layout = nx.shell_layout(self.graph)
	# 	nx.draw(self.graph, layout)
	# 	labels = {}
	# 	for id in self.graph.nodes():
	# 		labels[id] = str(id).split(":")[5].strip("]")
	# 	nx.draw_networkx_labels(self.graph, layout, labels)
	# 	plt.axis('off')
	# 	plt.savefig("graph.png")

	#creates a .dot file and parses it to a graph using graphviz
	#to use this install graphviz package and make sure dot is in your path
	def draw_graph(self, shape="circle", color="blue", penwidth=1, fullmac=False, graphname="graph.png"):
		"""
		Saves a snapshot of the current dodag tree to a dot file and creates a png figure from that

		:param shape: the shape of each node
		:param color: color of the lines between the nodes
		:param penwidth: width in pixels of the connecting lines
		:param fullmac: wether the full mac address needs to be displayed or only the last four letters
		:type fullmac: bool
		:param graphname: the name of the dot and png file to be created
		"""
		#setup the filestream and dot file
		dotfile = "snapshots/" + graphname.split(".")[0] + ".dot"
		stream = open(dotfile, 'w')
		stream.write("digraph Test {\n\tnode [shape = " + shape + "];\n\tsplines=false;\n")
		#iterate through the nodes
		for nid in self.graph.nodes():
			parent = self.get_parent(nid)
			if parent is None:
				continue
			# stream.write('\t' + parent + ' -> ' + str(id) +  ' [label="' + str(count) + '", color = ' + color + ', penwidth = ' + str(penwidth) + '];\n')
			#write the dot file
			if fullmac:
				stream.write('\t"' + str(parent) + '" -> "' + str(nid) +  '" [color = ' + color + ', penwidth = ' + str(penwidth) + '];\n')
			else:
				stream.write('\t"' + str(parent).split(":")[5].strip("]") + '" -> "' + str(nid).split(":")[5].strip("]") +  '" [color = ' + color + ', penwidth = ' + str(penwidth) + '];\n')
		stream.write("}\n")
		stream.close()
		#activate graphviz to create the graph from the dotfile
		call(["dot", "-Tpng", dotfile, "-o", "graphs/" + graphname])

	#detaches a node AND ALL ITS CHILDREN
	def detach_node(self, node_id):
		"""
		Detaches a node AND ALL ITS CHILDREN from the graph

		WARNING THIS FUNCTION IS RECURSIVE
		this means that for very large graphs it will either crash or run until infinite time because python does not implement tail recursion optimization
		for more information see:
		http://neopythonic.blogspot.com.au/2009/04/tail-recursion-elimination.html
		http://neopythonic.blogspot.com.au/2009/04/final-words-on-tail-calls.html

		:param node_id:
		:type node_id: :class: `node.NodeID`
		:return:
		"""

		if node_id in self.graph.nodes():
			#get all children and recursive call this function on them
			for neighbor in self.graph.neighbors(node_id):
				if 'child' in self.graph.edge[node_id][neighbor]:
					if self.graph.edge[node_id][neighbor]['child'] is not node_id:
						self.detach_node(self.graph.edge[node_id][neighbor]['child'])
			self.graph.remove_node(node_id)
			return True
		return False

	# returns the parent_id of the inputted child_id
	def get_neighbors(self, node):
		return self.graph.neighbors(node)

	def get_parent(self, child_id):
		if child_id in self.graph.nodes():
			for neighbor in self.graph.neighbors(child_id):
				if 'parent' in self.graph.edge[child_id][neighbor] and self.graph.edge[child_id][neighbor]['parent'] == neighbor:
					return neighbor
		return None

	# adds a node to the DoDAG graph and to the vizualized network graph
	def get_children(self, parent_id):
		if parent_id in self.graph.nodes():
			children = []
			for neighbor in self.graph.neighbors(parent_id):
				if 'child' in self.graph.edge[parent_id][neighbor] and self.graph.edge[parent_id][neighbor]['child'] == neighbor and 'parent' in self.graph.edge[parent_id][neighbor] and self.graph.edge[parent_id][neighbor]['parent'] == parent_id:
					children.append(neighbor)
			return children
		return None

	def attach_node(self, node_id):
		if node_id not in self.graph.nodes():
			self.graph.add_node(node_id)    # adds the node with node_id to the locally stored graph
			return True
		return False

	def check_node(self, node_id):
		"""
		checks if the node is already on the graph

		:param node_id: the node you want to be checked
		:type node_id: :class: `node.NodeID`
		:return: True if the node is on the graph, false if not
		"""
		return node_id in self.graph.nodes()


	def attach_child(self, child_id, parent_id):
		"""
		creates a parent child link in the graph

		:param child_id: the id of the child of the link
		:type child_id: :class: `node.NodeID`
		:param parent_id: the id of the parent of the link
		:type parent_id :class:` node.NodeID`
		:return: boolean

		"""
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
				elif self.graph.edge[child_id][neighbor]['parent'] == child_id and neighbor == parent_id:
					self.graph.remove_edge(child_id, neighbor)
				elif self.graph.edge[child_id][neighbor]['parent'] == parent_id:
					return False
		self.graph.add_edge(child_id, parent_id, parent=parent_id, child=child_id)
		return True

	def update_link(self, node, endpoint, metric, value):
		"""
		updates the statistics information on a link in the graph

		:param node:
		:param endpoint:
		:param metric:
		:param value:

		"""
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


	def get_node_depth(self, node_id):
		return nx.shortest_path(self.graph, node_id, self.root).__len__()-1 #TODO rewrite based on the parent-child relationship

	#ADDED BY FRANK
	def switch_parent(self, node_id, newparent_id):
		"""
		rewires a node to a different parent in the local dodag tree
		this is just a wrapper for the :func:`attach_child` as this already supports rewiring

		:param node_id:
		:type node_id: :class: `node.NodeID`
		:param newparent_id:
		:type newparent_id: :class: `node.NodeID`
		:return:
		"""
		self.attach_child(node_id, newparent_id)