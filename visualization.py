CWD = "D:\\g.exarchakos@tue.nl\\projects\\EIT ICT\\RICH\\RiSCHER"

def visualize(graph, metric):
	for n in graph.getUnderlyingGraph().getNodes():
		d = graph.underlyingGraph.getDegree(n)
		graph.underlyingGraph.getNode(n.getNodeData().getId()).getNodeData().setSize(100+20*d)

	for e in graph.getUnderlyingGraph().getEdges():
		value = e.getAttributes().getValue(metric)
		graph.getUnderlyingGraph().getEdge(e.getId()).getEdgeData().setLabel(metric+': '+str(value))
		graph.getUnderlyingGraph().getEdge(e.getId()).setWeight(value)


ED_METRICS = ['C-PRR', 'P-PRR', 'C-RSSI', 'P-RSSI', 'C-SLOT', 'P-SLOT']