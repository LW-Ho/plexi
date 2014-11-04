import txthings.coap as coap
from endpoint.client import Communicator
from resource.rpl import NodeID
import sys
from twisted.python import log

log.startLogging(sys.stdout)

c = Communicator()
to_node = NodeID('aaaa::212:7401:1:101', 5684)
uri = 'rpl/nd'
token = 1

c.OBSERVE(to_node, uri, token, c.test_callable)
c.GET(to_node, uri, token+1, c.test_callable)

uri = '6t/6/sf'
c.POST(to_node, uri, '{"ns":101}', token+1, c.test_callable)
uri = '6t/6/sf'
c.POST(to_node, uri, '{"ns":202}', token+1, c.test_callable)

#uri = '6t/6/cl'
#c.POST(to_node, uri, '{"co": 0, "lo": 10, "lt": 1, "fd": 0, "so": 1}', token+1, c.test_callable)
#uri = '6t/6/cl'
#c.POST(to_node, uri, '{"co": 0, "lo": 10, "lt": 1, "fd": 0, "so": 2}', token+1, c.test_callable)
#uri = '6t/6/cl'
#c.POST(to_node, uri, '{"co": 0, "lo": 10, "lt": 1, "fd": 0, "so": 3}', token+1, c.test_callable)
#uri = '6t/6/cl'
#c.POST(to_node, uri, '{"co": 0, "lo": 10, "lt": 1, "fd": 0, "so": 4}', token+1, c.test_callable)

uri = '6t/6/cl'
c.POST(to_node, uri, '{"co": 0, "lo": 10, "lt": 1, "fd": 0, "so": 1}', token+3, c.test_callable)
c.POST(to_node, uri, '{"co": 0, "lo": 10, "lt": 1, "fd": 0, "so": 1}', token+4, c.test_callable)



c.start()
