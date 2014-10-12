
class Slotframe(object):
	def __init__(self, name, slots):
		self.cell_container = []  # Will contain Cell objects assigned to this slotframe.
		self.slots = slots
		self.name = name
		self.fds = {}
		c_minimal = Cell(0, 0, 0, 0,None, 0, 7)  # TODO: do all the slotframes have the same minimal cell? Wouldn't that bring more conflicts?
		self.cell_container.append(c_minimal)

	def setAliasID(self, node, id):
		self.fds[node] = id

	def cell(self, so, co, owner):
		# TODO: return the Cell object with so, co, fd, and tx/rx
		pass

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
			if item.tx_node == node_id or item.rx_node == node_id:
				deleted_cell_container.append(item)  # add the deleted item to the repsective container
				self.cell_container.remove(item)  # remove the item from the cell_container
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