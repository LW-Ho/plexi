__author__ = 'Ioztelcan'

import networkx as nx

def nuke(dodag):
	pass

g = nx.Graph()

g.add_edge('a','b')
g.add_edge('a','c')
g.add_edge('c','d')
g.add_edge('d','f')
g.add_edge('d','e')

for i in reversed(list(nx.bfs_tree(g,'a'))):
	print i
