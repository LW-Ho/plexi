#include "Adwin.h"

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
