__author__ = "Dimitris Sarakiotis, Ilker Oztelcan, George Exarchakos"
__email__ = "d.sarakiotis@tue.nl, i.oztelcan@tue.nl, g.exarchakos@tue.nl"
__version__ = "0.0.11"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from resource import rpl

class Slotframe(object):
	def __init__(self, name, slots):
		self.cell_container = []  # Will contain Cell objects assigned to this slotframe.
		self.slots = slots
		self.name = name
		self.fds = {}   # will contain slotframe_ids in (key : value) format --> (node : sf_id)
		c_minimal = Cell(0, 0, None, None, None, 0, 7)  # TODO: do all the slotframes have the same minimal cell? Wouldn't that bring more conflicts?
		self.cell_container.append(c_minimal)

	def setAliasID(self, node, id):
		self.fds[node] = id

	def cell(self, **kwargs):
		matching_cells = []
		for i in self.cell_container:
			if 'slot' in kwargs.keys() and kwargs['slot'] != i.slot:
				continue
			if 'channel' in kwargs.keys() and kwargs['channel'] != i.channel:
				continue
			if 'link_option' in kwargs.keys() and kwargs['link_option'] != i.link_option:
				continue
			if 'cell_id' in kwargs.keys() and kwargs['cell_id'] != i.cell_id:
				continue
			if 'frame_id' in kwargs.keys() and kwargs['frame_id'] != i.slotframe_id:
				continue
			if 'tx_node' in kwargs.keys() and kwargs['tx_node'] != i.tx_node:
				continue
			if 'rx_node' in kwargs.keys() and kwargs['rx_node'] != i.rx_node:
				continue
			matching_cells.append(i)
		return matching_cells

	def allocate_to(self, node_id):
		all_cells = []  #This will contain all the dictionaries with cell information.

		for item in self.cell_container:

			if item.tx_node == node_id or item.rx_node == node_id:
				#cell_info = item.__dict__
				all_cells.append(item)

		return all_cells

	def delete_cell(self, node_id):
		deleted_cell_container = []
		for item in self.cell_container:
			if item.tx_node is None and item.rx_node is None:
				continue
			elif item.tx_node == node_id and item.rx_node is None:
				for j in self.cell_container:
					if j.tx_node is None and j.rx_node is None:
						continue
					if j.slot == item.slot and j.channel == item.channel and j.link_option == 9:
						deleted_cell_container.append(j)  # add the deleted item to the repsective container
				deleted_cell_container.append(item)  # add the deleted item to the repsective container
			elif item.tx_node is None and item.rx_node == node_id and item.link_option == 9:
				deleted_cell_container.append(item)  # add the deleted item to the repsective container
			elif (item.tx_node == node_id or item.rx_node == node_id) and item.link_option in [1, 2]: # TODO: remove the rpl.NodeID part. Make the whole software work only with NodeID types
				deleted_cell_container.append(item)  # add the deleted item to the repsective container
		for dltd in deleted_cell_container:
			self.cell_container.remove(dltd)
		return deleted_cell_container



class Cell(object):
	def __init__(self, so, co, tx, rx, fd, lt, lo):
		self.cell_id = None
		self.slotframe_id = fd
		self.channel = co
		self.tx_node = tx
		self.rx_node = rx
		self.slot = so
		self.link_type = lt
		self.link_option = lo
		self.pending = False

	@property
	def id(self):
		return self.cell_id

	@id.setter
	def id(self, cd):
		self.cell_id = cd

	def getID(self):  #Maybe a function like this gets the CellId assigned by 6top? Can include the POST command and reply will be the ID.
		pass

	def getInfo(self, cell_id):
		# returns all info about the cell with given id.
		pass

	def delete_cell(self, node_id):
		pass