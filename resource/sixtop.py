from coapthon2.resources.resource import Resource
import json


class SlotframeList(Resource):
	def __init__(self, name):
		if not isinstance(name, SlotframeList):
			super(SlotframeList, self).__init__(name=name, visible=True, observable=True, allow_children=True)
			self.add_content_type('application/json')
			self.frame_ids = 0
			self.frames = []
			self.payload = {'application/json': {f.id: f.size for f in self.frames}}
			self.tokens = {}
		else:
			super(SlotframeList, self).__init__(name)
			self.frame_ids = name.frame_ids
			self.frames = name.frames
			self.tokens = name.tokens

	def render_GET(self, request, query=None):
		# return nothing and a 4.04 Not Found error will be sent back
		# return a payload and a 2.05 Content will be sent back
		if not query:
			return {'Payload': self.payload}

	def render_POST(self, request, payload=None, query=None):
		# return nothing or -2 for INTERNAL_SERVER_ERROR
		# return -1 for METHOD_NOT_ALLOWED
		if payload:
			if request.token in self.tokens:
				return self.tokens[request.token]
			P = json.loads(payload)
			if isinstance(P, dict) and len(P) == 1 and 'ns' in P.keys():
				frame = Slotframe('6top.slotframe', self, P['ns'])
				self.frames.append(frame)
				self.payload = {'application/json': {f.id: f.size for f in self.frames}}
				self.tokens[request.token] = {"Payload": {'fd': frame.id}, 'Resource': frame}
				return {"Payload": {'fd': frame.id}, 'Resource': frame}

	def next(self):
		self.frame_ids += 1
		return self.frame_ids

	def erase(self, frame_id):
		counter = 0
		for k,v in self.tokens:
			if v['Resource'].id == frame_id:
				del self.tokens[k]
				break
		for f in self.frames:
			if f.id == frame_id:
				break
			counter += 1
		del self.frames[counter]


class Slotframe(Resource):
	def __init__(self, name, frame_container=None, slots=101):
		if not isinstance(name, Slotframe):
			super(Slotframe, self).__init__(name=name, visible=True, observable=True, allow_children=False)
			if isinstance(slots, (int, long)) and slots >= 1 and frame_container:
				self.add_content_type('application/json')
				self.container = frame_container
				self.id = self.container.next()
				self.path = str(self.id)
				self.size = slots
				self.payload = {'application/json': {'ns': self.size}}
			else:
				raise ValueError('Size of slotframe is at least 1 slot and should belong to a SlotframeList')
		else:
			super(Slotframe, self).__init__(name)
			self.container = name.container
			self.id = name.id
			self.size = name.size

	def render_GET(self, request, query=None):
		# return nothing and a 4.04 Not Found error will be sent back
		# return a payload and a 2.05 Content will be sent back
		return {'Payload': self.payload}

	def render_DELETE(self, request, query=None):
		self.container.erase(self.id)
		True


class CellList(Resource):
	def __init__(self, name):
		if not isinstance(name, CellList):
			super(CellList, self).__init__(name=name, visible=True, observable=True, allow_children=True)
			self.add_content_type('application/json')
			self.cell_ids = 0
			self.cells = []
			self.payload = {'application/json': {}}#c.id: {'so': c.so, 'co': c.co, 'lo': c.lo, 'fd': c.fd, 'lt': c.lt} for c in self.cells}}
			self.tokens = {}
		else:
			super(CellList, self).__init__(name)
			self.cell_ids = name.cell_ids
			self.cells = name.cells
			self.tokens = name.tokens

	def render_GET(self, request, query=None):
		# return nothing and a 4.04 Not Found error will be sent back
		# return a payload and a 2.05 Content will be sent back

		if not query:
			return {'Payload': self.payload}

	def render_POST(self, request, payload=None, query=None):
		# return nothing or -2 for INTERNAL_SERVER_ERROR
		# return -1 for METHOD_NOT_ALLOWED

		if payload:
			if request.token in self.tokens:
				return self.tokens[request.token]
			P = json.loads(payload)
			if isinstance(P, dict) and 'so' in P.keys() and 'co' in P.keys() and 'lo' in P.keys() and 'lt' in P.keys() and 'fd' in P.keys():
				cell = Cell('6top.cell', self, P['so'], P['co'], P['lo'], P['lt'], P['fd'])
				self.cells.append(cell)
				self.payload = {'application/json': {c.id: {'so': c.so, 'co': c.co, 'lo': c.lo, 'lt': c.lt, 'fd': c.fd} for c in self.cells}}
				self.tokens[request.token] = {"Payload": {'cd': cell.id}, 'Resource': cell}
				return {"Payload": {'cd': cell.id}, 'Resource': cell}

	def next(self):
		self.cell_ids += 1
		return self.cell_ids

	def erase(self, cell_id):
		counter = 0
		for k,v in self.tokens:
			if v['Resource'].id == cell_id:
				del self.tokens[k]
				break
		for c in self.cells:
			if c.id == cell_id:
				break
			counter += 1
		del self.cells[counter]


class Cell(Resource):
	def __init__(self, name, cell_container=None, so=None, co=None, lo=None, lt=None, fd=None):
		if not isinstance(name, Cell):
			super(Cell, self).__init__(name=name, visible=True, observable=True, allow_children=False)
			if isinstance(cell_container, CellList):
				self.add_content_type('application/json')
				self.container = cell_container
				self.id = self.container.next()
				self.path = str(self.id)
				self.so = so
				self.co = co
				self.lo = lo
				self.lt = lt
				self.fd = fd
				self.payload = {'application/json': {'so': self.so, 'co': self.co, 'lo': self.lo, 'lt': self.lt, 'fd': self.fd}}
			else:
				raise ValueError('A Cell should belong to a CellList')
		else:
			super(Cell, self).__init__(name)
			self.container = name.container
			self.id = name.id
			self.so = name.so
			self.co = name.co
			self.lo = name.lo
			self.lt = name.lt
			self.fd = name.fd

	def render_GET(self, request, query=None):
		# return nothing and a 4.04 Not Found error will be sent back
		# return a payload and a 2.05 Content will be sent back
		return {'Payload': self.payload}

	def render_DELETE(self, request, query=None):
		self.container.erase(self.id)
		True
