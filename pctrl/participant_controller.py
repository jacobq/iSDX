#  Author:
#  Arpit Gupta (Princeton)

import json
from netaddr import *
from peer import BGPPeer as BGPPeer
from supersets2 import SuperSets
from arp_proxy import arp_proxy

from ss_rule_scheme import *

LOG = True


class ParticipantController():
    def __init__(self, id, vmac_mode, dp_mode, sender, config_file, policy_file):
        # participant id
        self.id = id

        # Vmac encoding mode
        self.vmac_mode = vmac_mode

        # Dataplane mode---multi table or multi switch
        self.dp_mode = dp_mode

        # Initialize participant params
        self.cfg = {}
        """
        self.cfg = 
        {
            "Ports": 
            [
                {
                    "Id": X
                    "MAC": "XX:XX:XX:XX:XX:XX",
                    "IP": "X.X.X.X"
                }
            ],
            "Peers": [...],
            "ASN": X
        }
        """
        self.policies = {}

        # used for tagging outbound rules as belonging to us
        self.port0_mac = None

        # ExaBGP Peering Instance
        self.bgp_instance = None

        '''Each controller will parse the config
        and initialize the local params'''
        self.parse_config(config_file)
        # TODO: read the event handler socket info from the config itself
        self.eh_socket = ('localhost', 5555)

        # VNHs related params
        self.num_VNHs_in_use = 0
        self.VNH_2_prefix = {}
        self.prefix_2_VNH = {}
        self.VNHs = IPNetwork('172.0.1.1/24')

        # Superset related params
        if self.vmac_mode == 0:
            if LOG: print "Initializing SuperSets class"
            self.superset_instance = SuperSets(self.bgp_instance, participant)
        else:
            # TODO: create similar class for MDS
            if LOG: print "Initializing MDS class"

        else:
            # TODO: @Robert: decide what variables need to be initialized here for MDS
            self.prefix_mds = []
            self.mds_old=[]

        # Fetch information about Reference Monitor's Listener
        # TODO: Read from a config file
        # TODO: Figure out whether we'll need a socket or REST API to communicate with Reference Monitor
        self.refmon_config = ('localhost', 5555)
        # Communication with the Reference Monitor
        self.refmon_url = 'http://localhost:8080/??'ha
        # Keep track of flow rules pushed
        self.dp_pushed = []
        # Keep track of flow rules scheduled for push
        self.dp_queued = []

        # Fetch information about XRS Listener
        #TODO: read from a config file
        self.xrs_config = ('localhost', 5566)

        # class for sending flow mods to the reference monitor
        self.fm_builder = FlowModMsgBuilder(self.id, self.config.flanc_auth["key"])
        self.sender = sender



    def start(self):
        # Start arp proxy
        self.sdx_ap = arp_proxy(self)
        self.ap_thread = Thread(target=self.sdx_ap.start)
        self.ap_thread.daemon = True
        self.ap_thread.start()

        # Start the event Handler Module
        self.set_event_handler()

        # Send flow rules for initial policies to the SDX's Reference Monitor
        self.initialize_dataplane()
        self.push_dp()

    def initialize_dataplane(self):
        "Read the config file and update the queued policy variable"
        # TODO: @Robert: Bring your logic of pushing initial inbound policies for each participant here

        port_count = len(self.participant_2_portmac[self.id])

        rule_msgs = init_inbound_rules(self.id, self.policies, port_count)

        self.dp_queued.extend(rule_msgs[changes])

        return 0

    def push_dp(self):
        '''
        (1) Check if there are any policies queued to be pushed
        (2) Send the queued policies to reference monitor
        '''

        while len(self.dp_queued) > 0:
            mod = self.dp_queued.pop()

            self.fm_builder.add_flow_mod(**mod)

            self.dp_pushed.append(mod)

        self.sender.send(self.fm_builder.get_msg())


        return 0


    def stop(self):
        "Stop the Participants' SDN Controller"
        self.sdx_ap.stop()
        self.ap_thread.join()

        # TODO: Think of better way of terminating this listener
        self.listener_eh.close()


    def parse_config(self, config_file):
        "Locally parse the SDX config file for each participant"
        # TODO: Explore how we can make sure that each participant has its own config file
        config = None
        with open(config_file, 'r') as f:
            config = json.load(f)


        self.cfg = config[self.id]

        # used for tagging outbound rules as belonging to us
        self.port0_mac = self.cfg["Ports"][0]["MAC"]

        # TODO: this doesn't work
        self.policies = participant["policies"]


        # TODO: Make sure making peers_in == peers_out has no negative impact
        peers_in = self.cfg["Peers"]
        peers_out = peers_in

        self.bgp_instance = BGPPeer(self.cfg["ASN", self.cfg["Ports"], 
                                    peers_in, peers_out)



    def set_event_handler(self):
        '''Start the listener socket for network events'''
        self.listener_eh = Listener(self.eh_socket, authkey=None)
        ps_thread = Thread(target=self.start_eh)
        ps_thread.daemon = True
        ps_thread.start()

    def start_eh(self):
        '''Socket listener for network events '''
        print "Event Handler started for", self.id
        while True:
            conn_eh = self.listener_eh.accept()
            tmp = conn.recv()
            data = json.loads(tmp)

            # Starting a thread for independently processing each incoming network event
            event_processor_thread = Thread(target = process_event, args = [data])
            event_processor_thread.daemon = True
            event_processor_thread.start()

            # Send a message back to the sender.
            reply = "Event Received"
            conn_eh.send(reply)
            conn_eh.close()

    def process_event(self, data):
        "Locally process each incoming network event"
        reply = ''
        if 'bgp' in data:
            route = data['bgp']
            # Process the incoming BGP updates from XRS
            self.process_bgp_route(route)
        elif 'vmac' in data:
            # Process the vmac related change events
            self.process_vmac_events(data['vmac'])
        elif 'policy_change' in data:
            # Process the event requesting change of participants' policies
            self.process_policy_changes(data['policy_change'])

        return reply

    def process_vmac_events(self, data):
        "Process the incoming vmac "
        # TODO: Port the logic of superset_changed function to update the outbound policies

        # Not sure if this needs to be a separate function. Vmac events always immediately follow 
        # BGP events, and the amount of code needed is rather small.
        return 0

    def process_policy_changes(self, data):
        "Process the changes in participants' policies"
        # TODO: Implement the logic of dynamically changing participants' outbound and inbound policy
        return 0

    def process_bgp_route(self, route):
        "Process each incoming BGP advertisement"
        reply = ''
        # Map to update for each prefix in the route advertisement.
        updates = self.bgp_instance.update(route)

        # TODO: This step should be parallelized
        # TODO: The decision process for these prefixes is going to be same, we
        # should think about getting rid of such redundant computations.
        for update in updates:
            self.bgp_instance.decision_process_local(update)
            self.vnh_assignment(update)

        if self.vmac_mode == 0:
            # update supersets
            "Map these BGP updates to Flow Rules"
            ss_changes = self.superset_instance.update_supersets(updates)


            flow_msgs = update_outbound_rules(ss_changes, self.policies, 
                                              self.superset_instance, self.port0_mac)
            if flow_msgs["type"] == "new":
                pass
                "self.dp_queued.append(wipe all outbound)"
            self.dp_queued.extend(flow_msgs["changes"])

        else:
            # TODO: similar logic for MDS
            if LOG: print "Creating ctrlr messages for MDS scheme"

        if sdn_ctrlr_msgs:
            "Send sdn_ctrlr_msgs to participant's SDN controller as a network event"
            self.send_nw_event(sdn_ctrlr_msgs, 'vmac')

        changes, announcements = self.bgp_update_peers(updates)

        # Send gratuitous ARP responses
        for change in changes:
            self.sdx_ap.send_gratuitous_arp(change)

        # Tell Route Server that it needs to announce these routes
        for announcement in announcements:
            # TODO: Complete the logic for this function
            self.send_announcements(announcement)


        return reply

    def send_nw_event(self, sdn_ctrlr_msgs, tag):
        "Send the sdn_ctrlr_msgs back to event handler"
        out = {}
        out['vmac'] = msgs
        # TODO: Add the logic to send this message to Participant's event handler




    def send_announcements(self, announcement):
        "Send the announcements to XRS"
        print "Sending the announcements"

    def vnh_assignment(self, update):
        "Assign VNHs for the advertised prefixes"
        if self.vmac_mode == 0:
            " Superset"
            # TODO: Do we really need to assign a VNH for each advertised prefix?
            if ('announce' in update):
            prefix = update['announce']['prefix']

            if (prefix not in self.prefix_2_VNH):
                # get next VNH and assign it the prefix
                self.num_VNHs_in_use += 1
                vnh = str(self.VNHs[self.num_VNHs_in_use])

                self.prefix_2_VNH[prefix] = vnh
                self.VNH_2_prefix[vnh] = prefix
        else:
            "Disjoint"
            # TODO: @Robert: Place your logic here for VNH assignment for MDS scheme
            if LOG: print "VNH assignment called for disjoint vmac_mode"

    def bgp_update_peers(self, updates):
        # TODO: Verify if the new logic makes sense
        changes = []
        announcements = []
        for update in updates:
            if 'announce' in update:
                prefix = update['announce']['prefix']
            else:
                prefix = update['withdraw']['prefix']
            prev_route = self.rib["output"][prefix]
            best_route = self.rib["local"][prefix]
            best_route["next_hop"] = str(self.prefix_2_VNH[prefix])

            if ('announce' in update):
                # Check if best path has changed for this prefix
                if not bgp_routes_are_equal(best_route, prev_route):
                    # store announcement in output rib
                    self.delete_route("output", prefix)
                    self.add_route("output", prefix, best_route)

                    if prev_route:
                        changes.append({"participant": self.id,
                                        "prefix": prefix,
                                        "VNH": self.prefix_2_VNH[prefix])

                    # announce the route to each router of the participant
                    for port in self.cfg["Ports"]:
                        # TODO: Create a sender queue and import the announce_route function
                        announcements.append(announce_route(port["IP"], prefix, 
                                            route["next_hop"], route["as_path"]))

            elif ('withdraw' in update):
                # A new announcement is only needed if the best path has changed
                if best_route:
                    "There is a best path available for this prefix"
                    if not bgp_routes_are_equal(best_route, prev_route):
                        "There is a new best path available now"
                        # store announcement in output rib
                        self.delete_route("output", prefix)
                        self.add_route("output", prefix, best_route)
                        if prev_route:
                            changes.append({"participant": self.id,
                                            "prefix": prefix,
                                            "VNH": self.prefix_2_VNH[prefix]})
                        for port in self.cfg["Ports"]:
                                announcements.append(announce_route(port["IP"], 
                                                     prefix, best_route["next_hop"], 
                                                     best_route["as_path"]))

                else:
                    "Currently there is no best route to this prefix"
                    if prev_route:
                        # Clear this entry from the output rib
                        self.delete_route("output", prefix)
                        for port in self.cfg["Ports"]:
                            # TODO: Create a sender queue and import the announce_route function
                            announcements.append(withdraw_route(port["IP"], 
                                                                prefix, 
                                                                self.prefix_2_VNH[prefix]))

        return changes, announcements



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', help='the directory of the example')
    parser.add_argument('id', type=int,
                   help='participant id (integer)')
    parser.add_argument('vmac_mode', type=int,
                  help='VMAC encoding scheme: 0--Super Set, 1---Disjoint Set')
    parser.add_argument('dp_mode', type=int,
                    help='participant id (integer)')
    args = parser.parse_args()



    # locate config file
    # TODO: Separate the config files for each participant
    base_path = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                "..","examples",args.dir,"controller","sdx_config"))
    config_file = os.path.join(base_path, "sdx_global.cfg")

    # locate the participant's policy file as well
    policy_path = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "..","examples",args.dir,"controller","participant_policies"))

    policy_filenames_file = os.path.join(base_path, "sdx_policies.cfg")
    with open(policy_filenames_file, 'r') as f:
        policy_filenames = json.load(f)
    policy_filename = policy_filenames[str(args.id)]

    policy_file = os.path.join(base_path, policy_filename)




    print "Starting the controller ", str(args.id), " with config file: ", config_file
    print "And policy file: ", policy_file


    # start controller
    ctrlr = ParticipantController(args.id, args.vmac_mode, args.dp_mode, config_file)
    ctrlr_thread = Thread(target=ctrlr.start)
    ctrlr_thread.daemon = True
    ctrlr_thread.start()

    while ctrlr_thread.is_alive():
        try:
            ctrlr_thread.join(1)
        except KeyboardInterrupt:
            ctrlr.stop()
