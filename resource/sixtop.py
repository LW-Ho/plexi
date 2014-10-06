from coapthon2.resources.resource import Resource
import json

from util import parser, exception


class SlotframeList(Resource):
	def __init__(self, name, frame_size=None):
		if not isinstance(name, SlotframeList):
			super(SlotframeList, self).__init__(name=name, visible=True, observable=True, allow_children=False)
			self.add_content_type('application/json')
			self.frame_ids = 0
			self.frames = []
			if frame_size:
				self.frames = [(self.frame_ids, frame_size)]
				self.payload = {'application/json': self.frames}
		else:
			super(SlotframeList, self).__init__(name)
			self.frame_ids = name.frame_ids
			self.frames = name.frames

	def render_GET(self, request, query=None):
		# return nothing and a 4.04 Not Found error will be sent back
		# return a payload and a 2.05 Content will be sent back

		if not query:
			return {'Payload': self.payload}
		try:
			query_list = parser.query_to_dictionary(query)
			if len(query_list) > 1:
				raise exception.FormatError(query)
			frame_id = query_list.keys()[0]
			frame = [(i,j) for (i, j) in self.frames if i==query_list.keys()[0]]
			if frame:
				return {'Payload': [frame]}
			else:
				raise exception.RequestError(frame_id)
		except (exception.FormatError, TypeError, exception.RequestError):
			pass

	def render_POST(self, request, payload=None, query=None):
		# return nothing or -2 for INTERNAL_SERVER_ERROR
		# return -1 for METHOD_NOT_ALLOWED

		if payload:
			P = json.loads(payload)
			if len(P) == 1:
				self.frame_ids += 1
				self.frames.append((self.frame_ids, P[0]))
				return {"Payload": self.payload}

	def render_DELETE(self, request, query=None):
		return True


# class Slotframe(Resource):
# 	def __init__(self, resource_container, slots=101):
# 		super(Slotframe, self).__init__(name='Slotframe', visible=True, observable=True, allow_children=False)
# 		if not isinstance(slots, (int, long)) or slots < 1:
# 			raise ValueError('Size of slotframe is at least 1 slot')
# 		self.id = resource_container.newFrameID()
# 		self.required_content_type = 'text/plain'
# 		self.payload = {'text/plain': str(slots)}
#
# 	def render_GET(self, query=None):
# 		# return nothing and a 4.04 Not Found error will be sent back
# 		# return a payload and a 2.05 Content will be sent back
# 		return {'Payload': self.payload}
