import ctypes
from ctypes import cdll
import os
import exceptions

path = os.path.dirname(os.path.realpath(__file__))
# os.environ['PATH'] = os.path.dirname(__file__) + ';' + os.environ['PATH']
lib = cdll.LoadLibrary(path + '/libadwin.so')


class Adwin(object):
	# @classmethod
	# def from_param(cls, obj):
	# 	if obj is None:
	# 		raise exceptions.TypeError('Adwin should exist')
	# 	else:
	# 		return ctypes.pointer(obj)

	def __init__(self, M):
		self.obj = lib.adwin_create(M)

	def getEstimation(self):
		func = lib.adwin_estimation
		func.restype = ctypes.c_double
		return func(self.obj)

	def getVariance(self):
		func = lib.adwin_variance
		func.restype = ctypes.c_double
		return func(self.obj)

	def update(self, value):
		func = lib.adwin_update
		func.restype = ctypes.c_bool
		#func.argtypes = [Adwin, ctypes.c_float]
		return func(ctypes.pointer(self), float(value))

	def printout(self):
		lib.adwin_print(self.obj)

	def length(self):
		return lib.adwin_length(self.obj)

		# replaced by the ctypes above. no more need of boost.python library
		# def __bootstrap__():
		#    global __bootstrap__, __loader__, __file__
		#    import sys, pkg_resources, imp
		#    __file__ = pkg_resources.resource_filename(__name__,'adwin.so')
		#    __loader__ = None; del __bootstrap__, __loader__
		#    imp.load_dynamic(__name__,__file__)
		# __bootstrap__()
