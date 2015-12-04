#include "Adwin.h"

extern "C" {
    Adwin* adwin_create(int M) { return new Adwin(M); }
    double adwin_estimation(Adwin* win) { return win->getEstimation(); }
    double adwin_variance(Adwin* win) { return win->getVariance(); }
    bool adwin_update(Adwin* win, const double &value) { return win->update(value); }
    void adwin_print(Adwin* win) { win->print(); }
    int adwin_length(Adwin* win) { return win->length(); }
}

/**
 * works only if boost.python is installed. The above ctypes replace the below

#include <boost/python.hpp>

BOOST_PYTHON_MODULE(adwin)
{
	using namespace boost::python;
	class_<Adwin>("Adwin", init<int>())
        .def("getEstimation", &Adwin::getEstimation)
        .def("getVariance", &Adwin::getVariance)
		.def("update", &Adwin::update)
        .def("printout", &Adwin::print)
		.def("length", &Adwin::length)
    ;
}
*/