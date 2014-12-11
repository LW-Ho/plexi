PWD = "D:\g.exarchakos@tue.nl\projects\EIT ICT\RICH\RiSCHER"

ND_METRICS = []
ED_METRICS = []

for n in g.nodes:
	bc_slot = n.node.attributes.getValue('BC-SLOT')
	n.size = 120+bc_slot*20

