__author__ = 'frank'

from json import loads, dumps

class Event(object):
	def __init__(self, EventId="", SubjectId="", TimeStamp="", InfoString=""):
		self._EventId = EventId
		self._SubjectId = SubjectId
		self._TimeStamp = round(TimeStamp)
		self._InfoString = InfoString
		if InfoString != "":
			self._Info = loads(self._InfoString)
		else:
			self._Info = None

	def LoadJson(self,jsonstring):
		data = loads(jsonstring)
		self._EventId = data["EventId"]
		self._SubjectId = data["SubjectId"]
		self._TimeStamp = data["TimeStamp"]
		self._InfoString = data["InfoString"]
		self._Info = loads(self._InfoString)

	def AddInfo(self, key, value):
		self._Info[key] = value

	@property
	def EventId(self):
		return self._EventId

	@property
	def SubjectId(self):
		return self._SubjectId

	@property
	def TimeStamp(self):
		return self._TimeStamp

	@property
	def InfoString(self):
		return self._InfoString

	@property
	def Info(self):
		return self._Info

	def __str__(self):
		return dumps({"EventId":self._EventId, "SubjectId":self._SubjectId, "TimeStamp":self._TimeStamp, "InfoString":self._InfoString})