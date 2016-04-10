__author__ = 'Frank Boerman'
__email__ = "f.j.l.boerman@student.tue.nl"

#testfile for the dodag tree

from core.graph import DoDAG
from core.node import NodeID
import datetime

def DumpGraph(dodag):
	tijd = datetime.datetime.time(datetime.datetime.now())
	filename = str(tijd.hour) + ":" + str(tijd.minute) + ":" + str(tijd.second) + ".png"
	dodag.draw_graph(graphname="graphs/"+filename)

#the DoDAG itself
root = NodeID("aaaa::215:8d00:57:6486")
graph = DoDAG("TestGraph", root)

#some nodes
N1 = NodeID("aaaa::215:8d00:57:64ba")
N2 = NodeID("aaaa::215:8d00:57:64b7")
N3 = NodeID("aaaa::215:8d00:57:64a2")
N4 = NodeID("aaaa::215:8d00:57:64a7")
N5 = NodeID("aaaa::215:8d00:57:64a9")

#create a graph
graph.attach_child(N1,root)
graph.attach_child(N2,root)
graph.attach_child(N3,N1)
graph.attach_child(N4,N2)
graph.draw_graph(graphname="graphs/before.png")
graph.detach_node(N2)
graph.draw_graph(graphname="graphs/after.png")

#delete the root and create a new graph
graph.detach_node(root)

graph.draw_graph(graphname="graphs/shouldbeempty.png")

graph.attach_node(N1)
graph.attach_child(N2,N1)
graph.attach_child(N3,N1)
graph.draw_graph(graphname="graphs/before2.png")
graph.detach_node(N2)
graph.draw_graph(graphname="graphs/after2.png")