from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpidToStr
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.packet_base import packet_base
from pox.lib.packet.packet_utils import *
import pox.lib.packet as pkt
from pox.lib.recoco import Timer
import time
from pox.openflow.of_json import *
import struct

log = core.getLogger()

# s1-s2 measurements
s1s2_start_time = 0.0
s1s2_sent_time1 = 0.0
s1s2_sent_time2 = 0.0
s1s2_received_time1 = 0.0
s1s2_received_time2 = 0.0
s1s2_src_dpid = 0
s1s2_dst_dpid = 0
s1s2_mytimer = 0
s1s2_OWD1 = 0.0
s1s2_OWD2 = 0.0
s1s2_delay = 0

# s1-s3 measurements
s1s3_start_time = 0.0
s1s3_sent_time1 = 0.0
s1s3_sent_time2 = 0.0
s1s3_received_time1 = 0.0
s1s3_received_time2 = 0.0
s1s3_src_dpid = 0
s1s3_dst_dpid = 0
s1s3_mytimer = 0
s1s3_OWD1 = 0.0
s1s3_OWD2 = 0.0
s1s3_delay = 0

# s1-s4 measurements
s1s4_start_time = 0.0
s1s4_sent_time1 = 0.0
s1s4_sent_time2 = 0.0
s1s4_received_time1 = 0.0
s1s4_received_time2 = 0.0
s1s4_src_dpid = 0
s1s4_dst_dpid = 0
s1s4_mytimer = 0
s1s4_OWD1 = 0.0
s1s4_OWD2 = 0.0
s1s4_delay = 0

s1_dpid = 0
s2_dpid = 0
s3_dpid = 0
s4_dpid = 0
s5_dpid = 0

s1_p1 = 0
s1_p4 = 0
s1_p5 = 0
s1_p6 = 0
s2_p1 = 0
s3_p1 = 0
s4_p1 = 0

pre_s1_p1 = 0
pre_s1_p4 = 0
pre_s1_p5 = 0
pre_s1_p6 = 0
pre_s2_p1 = 0
pre_s3_p1 = 0
pre_s4_p1 = 0


# probe protocol packet definition; only timestamp field is present in the header (no payload part)
class myproto(packet_base):
  #My Protocol packet struct
  """
  myproto class defines our special type of packet to be sent all the way along including the link between the switches to measure link delays;
  it adds member attribute named timestamp to carry packet creation/sending time by the controller, and defines the 
  function hdr() to return the header of measurement packet (header will contain timestamp)
  """
  #For more info on packet_base class refer to file pox/lib/packet/packet_base.py

  def __init__(self):
    packet_base.__init__(self)
    self.timestamp=0

  def hdr(self, payload):
    return struct.pack('!I', self.timestamp) # code as unsigned int (I), network byte order (!, big-endian - the most significant byte of a word at the smallest memory address)


class Intent():
  def __init__(self, source, destination, delay):
    self.source = source
    self.destination = destination
    self.delay = delay
    
  def __repr__(self):
    msg = "Intent delay %d" % (self.delay)
    return msg

#generating intents
intent1 = Intent("h1", "10.0.0.4", 130)
intent2 = Intent("h2", "10.0.0.5", 90)
intent3 = Intent("h3", "10.0.0.6", 170)
intent4 = Intent("h2", "10.0.0.6", 50)
intent5 = Intent("h1", "10.0.0.4", 180)
intent6 = Intent("h3", "10.0.0.5", 30)
intent7 = Intent("h1", "10.0.0.6", 10)
intent8 = Intent("h2", "10.0.0.4", 20)
intent9 = Intent("h3", "10.0.0.4", 200)
intent10 = Intent("h2", "10.0.0.5", 100)
intents = [intent1, intent2, intent3, intent4, intent5, intent6, intent7, intent8, intent9, intent10]


class RoutingController():
  def __init__(self):
    self.intents = []
    self.delays = self.update_delays()

  def sort(self):
    self.intents.sort()
    print "[RoutingController] Intends sorted"

  def update_delays(self):
    self.delays = {
    "s2": s1s2_delay,
    "s3": s1s3_delay,
    "s4": s1s4_delay
    }
  
  def update(self):
    print "|| Updated links info"
    self.update_delays()
    delays_str = ", ".join(["{}: {}".format(k, v) for k, v in sorted(routingController.delays.items())])
    print "\n|| Delay on links going through: {" + delays_str + "}"

    self.routing()

  def routing(self):
      port_table ={'s2': 5, 's3': 6, 's4': 4}
      flows_by_switch = {"s2": 0, "s3": 0, "s4": 0}
      for intent in intents:
          possible_flows = [name_switch for name_switch, delay in self.delays.items() if int(intent.delay) > delay]
          result = "[INTENT] source: {}, destination: {}, required_delay: {}".format(intent.source, intent.destination, intent.delay)
          if not possible_flows:
              result += " Routing with random path. "
              possible_flows = ["s2", "s3", "s4"]
          flow = self.choose_link(possible_flows, flows_by_switch)
          result += " Sending through: {}".format(flow)
          flows_by_switch[flow] += 1
          self.msg(intent.destination, port_table[flow])
          print(result)

      flows_str = ", ".join(["{}: {}".format(k, v) for k, v in sorted(flows_by_switch.items())])
      print "|| Choosen switches {" + flows_str + "}"

  # load balancing
  def choose_link(self, possible_flows, flows):
      
      min_flow = possible_flows[0]
      min_value = flows[min_flow]
      for flow in possible_flows[1:]:
          if flows[flow] < min_value:
              min_flow = flow
      return min_flow


  def msg(self, destination, src_port):
    core.openflow.getConnection(s1_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    msg = of.ofp_flow_mod()
    msg.command=of.OFPFC_MODIFY_STRICT
    msg.priority =100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_dst = destination
    msg.actions.append(of.ofp_action_output(port = int(src_port)))
    core.openflow.getConnection(s1_dpid).send(msg)
    

routingController = RoutingController()
routingController.intents = intents
routingController.sort()
 
def getTheTime():  #function to create a timestamp
  flock = time.localtime()
  then = "[%s-%s-%s" %(str(flock.tm_year),str(flock.tm_mon),str(flock.tm_mday))
 
  if int(flock.tm_hour)<10:
    hrs = "0%s" % (str(flock.tm_hour))
  else:
    hrs = str(flock.tm_hour)
  if int(flock.tm_min)<10:
    mins = "0%s" % (str(flock.tm_min))
  else:
    mins = str(flock.tm_min)
 
  if int(flock.tm_sec)<10:
    secs = "0%s" % (str(flock.tm_sec))
  else:
    secs = str(flock.tm_sec)
 
  then +="]%s.%s.%s" % (hrs,mins,secs)
  return then
 
 
def _timer_func ():
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  core.openflow.getConnection(s1_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  core.openflow.getConnection(s2_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  core.openflow.getConnection(s3_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  core.openflow.getConnection(s4_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  # print getTheTime(), "sent the port stats request to s1_dpid"

  routingController.update()
  

  # This function is called periodically to send measurement-oriented messages to the switches.
  global s1s2_start_time, s1s2_sent_time1, s1s2_sent_time2, s1s2_src_dpid, s1s2_dst_dpid
 
  # the following executes only when a connection to 'switch0' exists (otherwise AttributeError can be raised)
  if s1s2_src_dpid !=0 and not core.openflow.getConnection(s1s2_src_dpid) is None:

    # send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
    core.openflow.getConnection(s1s2_src_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1s2_sent_time1=time.time() * 1000*10 - s1s2_start_time #sending time of stats_req: ctrl => switch0
    # print "sent_time1:", sent_time1

    # sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
    f = myproto() #create a probe packet object
    e = pkt.ethernet() #create L2 type packet (frame) object
    e.src = EthAddr("0:0:0:0:1:2")
    e.dst = EthAddr("0:0:0:0:2:1")
    e.type=0x5577 #set unregistered EtherType in L2 header type field, here assigned to the probe packet type 
    msg = of.ofp_packet_out() #create PACKET_OUT message object
    msg.actions.append(of.ofp_action_output(port=4)) #set the output port for the packet in switch0
    f.timestamp = int(time.time()*1000*10 - s1s2_start_time) #set the timestamp in the probe packet
    # print f.timestamp
    e.payload = f
    msg.data = e.pack()
    core.openflow.getConnection(s1s2_src_dpid).send(msg)
    #print "=====> probe sent: f=", f.timestamp, " after=", int(time.time()*1000*10 - s1s2_start_time), " [10*ms]"

  # the following executes only when a connection to 'switch1' exists (otherwise AttributeError can be raised)
  if s1s2_dst_dpid !=0 and not core.openflow.getConnection(s1s2_dst_dpid) is None:
    # send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
    core.openflow.getConnection(s1s2_dst_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1s2_sent_time2=time.time() * 1000*10 - s1s2_start_time #sending time of stats_req: ctrl => switch1
    # print "sent_time2:", sent_time2

  # This function is called periodically to send measurement-oriented messages to the switches.
  global s1s3_start_time, s1s3_sent_time1, s1s3_sent_time2, s1s3_src_dpid, s1s3_dst_dpid
 
  # the following executes only when a connection to 'switch0' exists (otherwise AttributeError can be raised)
  if s1s3_src_dpid !=0 and not core.openflow.getConnection(s1s3_src_dpid) is None:

    # send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
    core.openflow.getConnection(s1s3_src_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1s3_sent_time1=time.time() * 1000*10 - s1s3_start_time #sending time of stats_req: ctrl => switch0
    # print "sent_time1:", sent_time1

    # sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
    f = myproto() #create a probe packet object
    e = pkt.ethernet() #create L2 type packet (frame) object
    e.src = EthAddr("0:0:0:0:1:3")
    e.dst = EthAddr("0:0:0:0:3:1")
    e.type=0x5578 #set unregistered EtherType in L2 header type field, here assigned to the probe packet type 
    msg = of.ofp_packet_out() #create PACKET_OUT message object
    msg.actions.append(of.ofp_action_output(port=5)) #set the output port for the packet in switch0
    f.timestamp = int(time.time()*1000*10 - s1s3_start_time) #set the timestamp in the probe packet
    # print f.timestamp
    e.payload = f
    msg.data = e.pack()
    core.openflow.getConnection(s1s3_src_dpid).send(msg)
    #print "=====> probe sent: f=", f.timestamp, " after=", int(time.time()*1000*10 - s1s3_start_time), " [10*ms]"

  # the following executes only when a connection to 'switch1' exists (otherwise AttributeError can be raised)
  if s1s3_dst_dpid !=0 and not core.openflow.getConnection(s1s3_dst_dpid) is None:
    # send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
    core.openflow.getConnection(s1s3_dst_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1s3_sent_time2=time.time() * 1000*10 - s1s3_start_time #sending time of stats_req: ctrl => switch1
    # print "sent_time2:", sent_time2

  # This function is called periodically to send measurement-oriented messages to the switches.
  global s1s4_start_time, s1s4_sent_time1, s1s4_sent_time2, s1s4_src_dpid, s1s4_dst_dpid
 
  # the following executes only when a connection to 'switch0' exists (otherwise AttributeError can be raised)
  if s1s4_src_dpid !=0 and not core.openflow.getConnection(s1s4_src_dpid) is None:

    # send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
    core.openflow.getConnection(s1s4_src_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1s4_sent_time1=time.time() * 1000*10 - s1s4_start_time #sending time of stats_req: ctrl => switch0
    # print "sent_time1:", sent_time1

    # sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
    f = myproto() #create a probe packet object
    e = pkt.ethernet() #create L2 type packet (frame) object
    e.src = EthAddr("0:0:0:0:1:4")
    e.dst = EthAddr("0:0:0:0:4:1")
    e.type=0x5579 #set unregistered EtherType in L2 header type field, here assigned to the probe packet type 
    msg = of.ofp_packet_out() #create PACKET_OUT message object
    msg.actions.append(of.ofp_action_output(port=6)) #set the output port for the packet in switch0
    f.timestamp = int(time.time()*1000*10 - s1s4_start_time) #set the timestamp in the probe packet
    # print f.timestamp
    e.payload = f
    msg.data = e.pack()
    core.openflow.getConnection(s1s4_src_dpid).send(msg)
    #print "=====> probe sent: f=", f.timestamp, " after=", int(time.time()*1000*10 - s1s4_start_time), " [10*ms]"

  # the following executes only when a connection to 'switch1' exists (otherwise AttributeError can be raised)
  if s1s4_dst_dpid !=0 and not core.openflow.getConnection(s1s4_dst_dpid) is None:
    # send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
    core.openflow.getConnection(s1s4_dst_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1s4_sent_time2=time.time() * 1000*10 - s1s4_start_time #sending time of stats_req: ctrl => switch1
    # print "sent_time2:", sent_time2


def _handle_portstats_received (event):

  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global s1_p1,s1_p4, s1_p5, s1_p6, s2_p1, s3_p1, s4_p1
  global pre_s1_p1,pre_s1_p4, pre_s1_p5, pre_s1_p6, pre_s2_p1, pre_s3_p1, pre_s4_p1

  if event.connection.dpid==s1_dpid: # The DPID of one of the switches involved in the link
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s1_p1=s1_p1
          s1_p1=f.rx_packets
          # print "s1_p1->","TxDrop:", f.tx_dropped,"RxDrop:",f.rx_dropped,"TxErr:",f.tx_errors,"CRC:",f.rx_crc_err,"Coll:",f.collisions,"Tx:",f.tx_packets,"Rx:",f.rx_packets
        if f.port_no==4:
          pre_s1_p4=s1_p4
          s1_p4=f.tx_packets
          # s1_p4=f.tx_bytes
          # print "s1_p4->","TxDrop:", f.tx_dropped,"RxDrop:",f.rx_dropped,"TxErr:",f.tx_errors,"CRC:",f.rx_crc_err,"Coll:",f.collisions,"Tx:",f.tx_packets,"Rx:",f.rx_packets
        if f.port_no==5:
          pre_s1_p5=s1_p5
          s1_p5=f.tx_packets
        if f.port_no==6:
          pre_s1_p6=s1_p6
          s1_p6=f.tx_packets
 
  if event.connection.dpid==s2_dpid:
     for f in event.stats:
       if int(f.port_no)<65534:
         if f.port_no==1:
           pre_s2_p1=s2_p1
           s2_p1=f.rx_packets
           # s2_p1=f.rx_bytes
     # print getTheTime(), "s1_p4(Sent):", (s1_p4-pre_s1_p4), "s2_p1(Received):", (s2_p1-pre_s2_p1)
 
  if event.connection.dpid==s3_dpid:
     for f in event.stats:
       if int(f.port_no)<65534:
         if f.port_no==1:
           pre_s3_p1=s3_p1
           s3_p1=f.rx_packets
     # print getTheTime(), "s1_p5(Sent):", (s1_p5-pre_s1_p5), "s3_p1(Received):", (s3_p1-pre_s3_p1)

  if event.connection.dpid==s4_dpid:
     for f in event.stats:
       if int(f.port_no)<65534:
         if f.port_no==1:
           pre_s4_p1=s4_p1
           s4_p1=f.rx_packets
     # print getTheTime(), "s1_p6(Sent):", (s1_p6-pre_s1_p6), "s4_p1(Received):", (s4_p1-pre_s4_p1)



  global s1s2_start_time, s1s2_sent_time1, s1s2_sent_time2, s1s2_received_time1, s1s2_received_time2, s1s2_src_dpid, s1s2_dst_dpid, s1s2_OWD1, s1s2_OWD2

  s1s2_received_time = time.time() * 1000*10 - s1s2_start_time
   # measure T1 as of lab guide
  if event.connection.dpid == s1s2_src_dpid:
    s1s2_OWD1=0.5*(s1s2_received_time - s1s2_sent_time1)
     # print "OWD1: ", OWD1, "ms"s
   # measure T2 as of lab guide
  elif event.connection.dpid == s1s2_dst_dpid:
    s1s2_OWD2=0.5*(s1s2_received_time - s1s2_sent_time2) #originally sent_time1 was here
     # print "OWD2: ", OWD2, "ms"


  global s1s3_start_time, s1s3_sent_time1, s1s3_sent_time2, s1s3_received_time1, s1s3_received_time2, s1s3_src_dpid, s1s3_dst_dpid, s1s3_OWD1, s1s3_OWD2

  s1s3_received_time = time.time() * 1000*10 - s1s3_start_time
   # measure T1 as of lab guide
  if event.connection.dpid == s1s3_src_dpid:
    s1s3_OWD1=0.5*(s1s3_received_time - s1s3_sent_time1)
     # print "OWD1: ", OWD1, "ms"s
   # measure T2 as of lab guide
  elif event.connection.dpid == s1s3_dst_dpid:
    s1s3_OWD2=0.5*(s1s3_received_time - s1s3_sent_time2) #originally sent_time1 was here
     # print "OWD2: ", OWD2, "ms"


  global s1s4_start_time, s1s4_sent_time1, s1s4_sent_time2, s1s4_received_time1, s1s4_received_time2, s1s4_src_dpid, s1s4_dst_dpid, s1s4_OWD1, s1s4_OWD2

  s1s4_received_time = time.time() * 1000*10 - s1s4_start_time
   # measure T1 as of lab guide
  if event.connection.dpid == s1s4_src_dpid:
    s1s4_OWD1=0.5*(s1s4_received_time - s1s4_sent_time1)
     # print "OWD1: ", OWD1, "ms"s
   # measure T2 as of lab guide
  elif event.connection.dpid == s1s4_dst_dpid:
    s1s4_OWD2=0.5*(s1s4_received_time - s1s4_sent_time2) #originally sent_time1 was here
     # print "OWD2: ", OWD2, "ms"


    

def _handle_ConnectionUp (event):
  # waits for connections from all switches, after connecting to all of them it starts a round robin timer for triggering h1-h4 routing changes
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid, s1s2_src_dpid, s1s2_dst_dpid, s1s3_src_dpid, s1s3_dst_dpid, s1s4_src_dpid, s1s4_dst_dpid
  print "ConnectionUp: ",dpidToStr(event.connection.dpid)
 
  # remember the connection dpid for the switch
  for m in event.connection.features.ports:
    if m.name == "s1-eth1":
      # s1_dpid: the DPID (datapath ID) of switch s1;
      s1_dpid = event.connection.dpid
      print "s1_dpid=", s1_dpid
    elif m.name == "s2-eth1":
      s2_dpid = event.connection.dpid
      s1s2_dst_dpid = event.connection.dpid
      print "s2_dpid=", s2_dpid
      print "s1s2_dst_dpid=", s1s2_dst_dpid
    elif m.name == "s3-eth1":
      s3_dpid = event.connection.dpid
      s1s3_dst_dpid = event.connection.dpid
      print "s3_dpid=", s3_dpid
      print "s1s3_dst_dpid=", s1s3_dst_dpid
    elif m.name == "s4-eth1":
      s4_dpid = event.connection.dpid
      s1s4_dst_dpid = event.connection.dpid
      print "s4_dpid=", s4_dpid
      print "s1s4_dst_dpid=", s1s4_dst_dpid
    elif m.name == "s5-eth1":
      s5_dpid = event.connection.dpid
      print "s5_dpid=", s5_dpid
    elif m.name == "s1-eth4":
      s1s2_src_dpid = event.connection.dpid
      print "s1s2_src_dpid=", s1s2_src_dpid
    elif m.name == "s1-eth5":
      s1s3_src_dpid = event.connection.dpid
      print "s1s3_src_dpid=", s1s3_src_dpid
    elif m.name == "s1-eth6":
      s1s4_src_dpid = event.connection.dpid
      print "s1s4_src_dpid=", s1s4_src_dpid
 
  # start 1-second recurring loop timer for round-robin routing changes; _timer_func is to be called on timer expiration to change the flow entry in s1
  if s1_dpid!=0 and s2_dpid!=0 and s3_dpid!=0 and s4_dpid!=0 and s5_dpid!=0:
    Timer(1, _timer_func, recurring=True)

 
def _handle_PacketIn(event):
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
 
  packet=event.parsed
  # print "_handle_PacketIn is called, packet.type:", packet.type, " event.connection.dpid:", event.connection.dpid

  global s1s2_start_time, s1s2_OWD1, s1s2_OWD2, s1s2_delay

  s1s2_received_time = time.time() * 1000*10 - s1s2_start_time #amount of time elapsed from start_time
 
  if packet.type==0x5577 and event.connection.dpid==s1s2_dst_dpid: #0x5577 is unregistered EtherType, here assigned to probe packets
    # Process a probe packet received in PACKET_IN message from 'switch1' (dst_dpid), previously sent to 'switch0' (src_dpid) in PACKET_OUT.

    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
    #print "[ms*10]: received_time=", int(s1s2_received_time), ", d=", d, ", OWD1=", int(s1s2_OWD1), ", OWD2=", int(s1s2_OWD2)
    s1s2_delay = int(s1s2_received_time - d - s1s2_OWD1 - s1s2_OWD2)/10
    # print "s1-s2 delay:", s1s2_delay, "[ms] <=====" # divide by 10 to normalise to milliseconds


  global s1s3_start_time, s1s3_OWD1, s1s3_OWD2, s1s3_delay

  s1s3_received_time = time.time() * 1000*10 - s1s3_start_time #amount of time elapsed from start_time
 
  if packet.type==0x5578 and event.connection.dpid==s1s3_dst_dpid: #0x5577 is unregistered EtherType, here assigned to probe packets
    # Process a probe packet received in PACKET_IN message from 'switch1' (dst_dpid), previously sent to 'switch0' (src_dpid) in PACKET_OUT.

    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
    #print "[ms*10]: received_time=", int(s1s3_received_time), ", d=", d, ", OWD1=", int(s1s3_OWD1), ", OWD2=", int(s1s3_OWD2)
    s1s3_delay = int(s1s3_received_time - d - s1s3_OWD1 - s1s3_OWD2)/10
    # print "s1-s3 delay:", s1s3_delay, "[ms] <=====" # divide by 10 to normalise to milliseconds
  

  global s1s4_start_time, s1s4_OWD1, s1s4_OWD2, s1s4_delay

  s1s4_received_time = time.time() * 1000*10 - s1s4_start_time #amount of time elapsed from start_time
 
  if packet.type==0x5579 and event.connection.dpid==s1s4_dst_dpid: #0x5577 is unregistered EtherType, here assigned to probe packets
    # Process a probe packet received in PACKET_IN message from 'switch1' (dst_dpid), previously sent to 'switch0' (src_dpid) in PACKET_OUT.

    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
    #print "[ms*10]: received_time=", int(s1s4_received_time), ", d=", d, ", OWD1=", int(s1s4_OWD1), ", OWD2=", int(s1s4_OWD2)
    s1s4_delay = int(s1s4_received_time - d - s1s4_OWD1 - s1s4_OWD2)/10
    # print "s1-s4 delay:", s1s4_delay, "[ms] <=====" # divide by 10 to normalise to milliseconds
  


  # Below, set the default/initial routing rules for all switches and ports.
  # All rules are set up in a given switch on packet_in event received from the switch which means no flow entry has been found in the flow table.
  # This setting up may happen either at the very first pactet being sent or after flow entry expirationn inn the switch
 
  if event.connection.dpid==s1_dpid:
     a=packet.find('arp')					# If packet object does not encapsulate a packet of the type indicated, find() returns None
     if a and a.protodst=="10.0.0.1":
       msg = of.ofp_packet_out(data=event.ofp)			# Create packet_out message; use the incoming packet as the data for the packet out
       msg.actions.append(of.ofp_action_output(port=1))		# Add an action to send to the specified port
       event.connection.send(msg)				# Send message to switch
 
     if a and a.protodst=="10.0.0.2":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=2))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.3":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=3))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.4":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=4))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.5":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=5))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.6":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=6))
       event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800		# rule for IP packets (x0800)
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.2"
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.3"
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 1
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.4"
     msg.actions.append(of.ofp_action_output(port = 4))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.5"
     msg.actions.append(of.ofp_action_output(port = 5))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.6"
     msg.actions.append(of.ofp_action_output(port = 6))
     event.connection.send(msg)
 
  elif event.connection.dpid==s2_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806		# rule for ARP packets (x0806)
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
  elif event.connection.dpid==s3_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
  
  elif event.connection.dpid==s4_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
  elif event.connection.dpid==s5_dpid: 
     a=packet.find('arp')
     if a and a.protodst=="10.0.0.1":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=1))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.2":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=2))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.3":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=3))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.4":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=4))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.5":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=5))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.6":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=6))
       event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 6
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.2"
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.3"
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.4"
     msg.actions.append(of.ofp_action_output(port = 4))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.5"
     msg.actions.append(of.ofp_action_output(port = 5))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.6"
     msg.actions.append(of.ofp_action_output(port = 6))
     event.connection.send(msg)

def launch ():
  global s1s2_start_time, s1s3_start_time, s1s4_start_time
  s1s2_start_time = time.time() * 1000*10
  s1s3_start_time = s1s2_start_time
  s1s4_start_time = s1s2_start_time
  # core is an instance of class POXCore (EventMixin) and it can register objects.
  # An object with name xxx can be registered to core instance which makes this object become a "component" available as pox.core.core.xxx.
  # For examples see e.g. https://noxrepo.github.io/pox-doc/html/#the-openflow-nexus-core-openflow 
  core.openflow.addListenerByName("PortStatsReceived",_handle_portstats_received) # listen for port stats , https://noxrepo.github.io/pox-doc/html/#statistics-events
  core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp) # listen for the establishment of a new control channel with a switch, https://noxrepo.github.io/pox-doc/html/#connectionup
  core.openflow.addListenerByName("PacketIn",_handle_PacketIn) # listen for the reception of packet_in message from switch, https://noxrepo.github.io/pox-doc/html/#packetin
