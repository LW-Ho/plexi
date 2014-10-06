class FormatError(Exception):
	def __init__(self, value):
		self.value = value
		self.message = 'Inappropriate format of input value: '+self.value

class RequestError(Exception):
	def __init__(self, value):
		self.value = value
		self.message = 'Inappropriate request received: '+str(self.value)