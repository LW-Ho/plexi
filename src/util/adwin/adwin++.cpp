#include "Adwin.h"

#include <boost/python.hpp>

BOOST_PYTHON_MODULE(adwin)
{
	using namespace boost::python;
	class_<Adwin>("Adwin", init<int>())
        .def("getEstimation", &Adwin::getEstimation)  // Add a regular member function.
		.def("update", &Adwin::update)
        .def("printout", &Adwin::print)
		.def("length", &Adwin::length)
    ;
}
