class FormatError(Exception):
	def __init__(self, value):
		self.value = value
		self.message = 'Inappropriate format of input value: '+self.value

	def __str__(self):
		return self.message

class RequestError(Exception):
	def __init__(self, value):
		self.value = value
		self.message = 'Inappropriate request received: '+str(self.value)

	def __str__(self):
		return self.message

class UnsupportedCase(Exception):
	def __init__(self, value):
		self.value = value

	def __str__(self):
		return str(self.value)
