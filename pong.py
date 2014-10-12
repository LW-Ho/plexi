from twisted.internet import reactor
from endpoint.server import LBRServer, NodeServer
import networkx
from resource.rpl import NodeID
import netaddr


def main():
	graph = networkx.Graph(name='RICHNET')
	root = NodeID('127.0.0.1', 5683)
	# root = NodeID('::1', 5683)
	graph.add_node(root)
	A = NodeID('127.0.0.1', 56831)
	# A = NodeID('::1', 56831)
	graph.add_node(A)
	graph.add_edge(root, A, parent=root, child=A)
	B = NodeID('127.0.0.1', 56832)
	# B = NodeID('::1', 56832)
	graph.add_node(B)
	graph.add_edge(root, B, parent=root, child=B)

	graph.node[root]['server'] = NodeServer(graph, root)
	graph.node[A]['server'] = NodeServer(graph, A)
	graph.node[B]['server'] = NodeServer(graph, B)


	reactor.listenUDP(root.port, graph.node[root]['server'], root.ip)
	reactor.listenUDP(A.port, graph.node[A]['server'], A.ip)
	reactor.listenUDP(B.port, graph.node[B]['server'], B.ip)
	reactor.run()

if __name__ == '__main__':
	main()