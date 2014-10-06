from twisted.internet import reactor
from endpoint.server import LBRServer, NodeServer
import networkx
from resource.rpl import NodeID


def main():
	graph = networkx.Graph(name='Fake RICH Network')
	root = NodeID('127.0.0.1', 5683)
	graph.add_node(root, server=LBRServer(graph))
	A = NodeID('127.0.0.1', 56831)
	graph.add_node(A, server=NodeServer(graph, A, root))
	graph.add_edge(root, A, parent=root)
	B = NodeID('127.0.0.1', 56832)
	graph.add_node(B, server=NodeServer(graph, B, root))
	graph.add_edge(root, B, parent=root)


	reactor.listenUDP(root.port, graph.node[root]['server'], root.ip)
	reactor.listenUDP(A.port, graph.node[A]['server'], A.ip)
	reactor.listenUDP(B.port, graph.node[B]['server'], B.ip)
	reactor.run()

if __name__ == '__main__':
	main()