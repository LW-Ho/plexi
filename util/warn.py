__author__ = "George Exarchakos"
__version__ = "0.0.1"
__email__ = "g.exarchakos@tue.nl"
__credits__ = ["Michael Chermside"]
__copyright__ = "Copyright 2014, The RICH Project"
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

import warnings

def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emmitted
    when the function is used."""
    def newFunc(*args, **kwargs):
        warnings.warn("Call to deprecated function %s." % func.__name__,
                      category=DeprecationWarning)
        return func(*args, **kwargs)
    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc