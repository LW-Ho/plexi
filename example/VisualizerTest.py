from util import logger
import logging
from util.Visualizer import FrankFancyStreamingInterface
import os.path
from core.slotframe import Slotframe, Cell
import time

logg = logging.getLogger('RiSCHER')
logg.setLevel(logging.DEBUG)

consoleLogger = logging.StreamHandler()
consoleLogger.setFormatter(logging.Formatter(fmt='%(asctime)s.%(msecs)03d\t%(levelname)s: %(message)s', datefmt='%H:%M:%S'))
consoleLogger.setLevel(logging.DEBUG)

temp = logging.getLogger('zmq')
temp.setLevel(logging.DEBUG)
temp.addHandler(consoleLogger)

if __name__ == '__main__':
	visualizer = {
		"name"	:	"plexi1",
		"Key"	:	os.path.join("keys", "plexi1.key_secret"),
		"VHost"	:	"192.168.64.1"
	}
	logg.info("Starting VisualizerTest")

	logg.info("Booting Streamer Interface")
	Streamer = FrankFancyStreamingInterface(visualizer["name"], None, visualizer["VHost"],ZeromqHost="*", root_id="n1")
	logg.info("Streamer Interface booted")
	time.sleep(5)
	Streamer.RegisterFrame(11, "broadcast")
	Streamer.RegisterFrames([{
		"id"	: "broadcast",
		"cells"	: 11
	}])
	time.sleep(5)
	Streamer.AddNode("n1", "root")
	time.sleep(5)
	Streamer.AddNode("n2", "n1")
	time.sleep(5)
	Streamer.AddNode("n3", "n1")
	Streamer.DumpDotData()
	time.sleep(5)
	Streamer.ChangeCell("n1", 0, 0, "broadcast", "cell", 1)
	time.sleep(5)
	Streamer.ChangeCell("n2", 0, 1, "broadcast", "cell", 1)
	time.sleep(5)
	Streamer.ChangeCell("n3", 0, 2, "broadcast", "cell", 1)
	time.sleep(5)
	Streamer.RewireNode("n3", "n1", "n2")
	Streamer.DumpDotData()
	time.sleep(5)
	Streamer.RemoveNode("n3")
	Streamer.DumpDotData()
	time.sleep(5)
	if hasattr(Streamer, 'auth'):
		Streamer.auth.stop()
	logg.info("VisualizerTest done")
