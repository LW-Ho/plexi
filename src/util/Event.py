__author__ = 'frank'

from json import loads

class Event(object):
	def __init__(self, EventId, SubjectId, TimeStamp, InfoString):
		self._EventId = EventId
		self._SubjectId = SubjectId
		self._TimeStamp = TimeStamp
		self._InfoString = InfoString

	@property
	def EventId(self):
		return self._EventId

	@property
	def Subjectid(self):
		return self._SubjectId

	@property
	def TimeStamp(self):
		return self._TimeStamp

	@property
	def InfoString(self):
		return self._InfoString

	@property
	def Info(self):
		return loads(self._InfoString)