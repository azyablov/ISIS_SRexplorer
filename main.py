"""
The scipt is used to draw ISIS SR domain graph.
"""

import sys
from pysros.management import sros, connect, Connection
# Wrappers
from pysros.wrappers import Container
# Exceptions
from pysros.exceptions import SrosMgmtError, InvalidPathError
from pysros.exceptions import ModelProcessingError
from graph import VNode, VEdge
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import re
from typing import List, Dict, Tuple
import yaml
import numpy as np


def get_connection(host: str, user: str, pwd: str, y_dir: str = "./7x50_YangModels/YANG", port: int = 830) -> Connection:
    """Function definition to obtain a Connection object to a specific SROS NE.
    :parameter host: The hostname or IP address of the SR OS node.
    :type host: str
    :paramater user: SROS username.
    :type user: str
    :paramater pwd: SROS password.
    :type pwd: str
    :parameter port: NETCONF TCP port on SROS NE.
    :type port: int
    :returns: Connection object for the SR OS node.
    :rtype: :py:class:`pysros.management.Connection`
    """
    connection_object: Connection
    if sros():
        connection_object = connect()
    else:
        try:
            connection_object = connect(
                host=host, port=port, username=user, password=pwd, timeout=30, hostkey_verify=False,
                yang_directory=y_dir
            )
        except RuntimeError as rt_err:
            print(f"Failed to connect to {host}:{port}. Error: {rt_err}")
            sys.exit(101)
        except ModelProcessingError as md_err:
            print(f"Failed to create model-driven schema for {host}:{port}. Error: {md_err}")
            sys.exit(102)
    return connection_object


def load_config(filename: str = 'srgraph.yml') -> dict:
    """Function definition to load configuration from YAML file.
    :parameter filename: Name of the YAML file.
    :type filename: str
    :returns: Configuration dictionary.
    :rtype: dict
    """
    with open(filename, 'r') as f:
        config = yaml.safe_load(f)
    return config

def sys_id_in_nodes(nodes: List[VNode], system_id: str) -> bool:
    """Function definition to check if system id is in the list of nodes.
    :parameter nodes: List of nodes.
    :type nodes: List[VNode]
    :parameter system_id: System ID to check.
    :type system_id: str
    :returns: True if system ID is in the list of nodes, False otherwise.
    :rtype: bool
    """
    idx = 0
    assert type(system_id) == str
    for node in nodes:
        if node.system_id == system_id:
            return True
        idx += 1
    return False

def sys_to_idx(nodes: List[VNode], system_id: str) -> int:
    """Function definition to get index of the node in the list of nodes.
    :parameter nodes: List of nodes.
    :type nodes: List[VNode]
    :parameter system_id: System ID to check.
    :type system_id: str
    :returns: Index of the node in the list of nodes.
    :rtype: int
    """
    idx = 0
    assert type(system_id) == str
    for node in nodes:
        if node.system_id == system_id:
            return idx
        idx += 1
    return -1


def name_to_idx(nodes: List[VNode], name: str) -> int:
    """Function definition to get index of the node by name.
    :parameter nodes: List of nodes.
    :type nodes: List[VNode]
    :parameter name: Name of the node to check.
    :type name: str
    :returns: Index of the node in the list of nodes.
    :rtype: int
    """
    idx = 0
    name = name.strip()
    assert type(name) == str
    for node in nodes:
        if node.name == name:
            return idx
        idx += 1
    return -1


def get_inf_adjs(isis: Container, nodes: List[VNode], adj_martix: List[List[VEdge]]) -> List[VEdge]:
    """Function definition to get adjacency data from ISIS container.
    :parameter isis: ISIS container.
    :type isis: Container
    :parameter nodes: List of nodes.
    :type nodes: List[VNode]
    :parameter adjs: List of adjacencies.
    :type adjs: List[VEdge]
    :parameter adj_martix: Adjacency matrix.
    :type adj_martix: List[List[int]]
    :returns: List of adjacency labels.
    :rtype: List[str]
    """
    # System ID of the current node (operational).
    node_id = isis.data['oper-system-id'].data
    adjs: List[VEdge] = []
    # Iterating over all infs and adjacencies
    for inf in isis.data['interface']:
        inf_name = isis.data['interface'][inf]['interface-name'].data
        if 'adjacency' in isis.data['interface'][inf].data:
            nei_snpa = isis.data['interface'][inf]['adjacency'][1]['neighbor']['snpa-address'].data
            # Eliciting adjacency data
            adj = isis.data['interface'][inf]['adjacency'][1]
            nbr_id = ''
            adj_sid = 0

            if adj.data['oper-state'].data == 'up': # proceed if adjacency up
                nbr_id = adj.data['neighbor'].data['system-id'].replace('0x','') # normalise nbr_id
                nbr_id = '.'.join([nbr_id[i:i+4] for i in range(0, len(nbr_id), 4)]) # normalise nbr_id
                if not sys_id_in_nodes(nodes, nbr_id): # check if nbr_id in nodes
                    continue # if not, skip it, bcz multi-level topology is not supported now
                adj_sid = adj.data['sr-ipv4'].data['sid-value'].data # get adj SID
                src_node_idx, dst_node_idx = sys_to_idx(nodes, node_id), sys_to_idx(nodes, nbr_id) # get indexes of the nodes in the list of nodes
                ve = VEdge(nodes[src_node_idx], nodes[dst_node_idx], adj_sid) # create adjacency object
                ve.inf_name = inf_name # add interface name to adjacency object
                ve.nei_snpa = nei_snpa # add neighbor SNPA to adjacency object
                if adj_martix[src_node_idx][dst_node_idx] is None: # check if adjacency matrix is empty
                    adj_martix[src_node_idx][dst_node_idx] = ve # fill in adjacency matrix with adj SID (the first found will be used)
                adjs.append(ve) # add adjacency to the list of adjacencies
    return adjs


def draw_edges(net_DiGr: nx.Graph, pos: Dict, ax: plt.Axes, route: List[VNode] = []):
    """"Function definition to draw edges with labels for directed graph.
    :parameter net_DiGr: Directed graph.
    :type net_DiGr: nx.Graph
    :parameter pos: Position of the nodes.
    :type pos: Dict
    :parameter ax: Axes object.
    :type ax: plt.Axes
    :returns: None
    :rtype: None
    """
    edge_labels = {(u, v, d['inf_mac']): d for u, v, d in net_DiGr.edges(data=True)} # get edge labels per node-pair-inf combination (inf_mac) to count multiple point-to-point links between the same nodes.
    visited_adj: List[Tuple[VNode, VNode, str]] = []
    visited_pairs: List[Tuple[VNode, VNode]] = []
    
    for u, v, m in edge_labels:
        if (u, v, m) in visited_adj:
            continue
        snpa = edge_labels[(u, v, m)]['nei_snpa'] # get neighbor SNPA
        inf = edge_labels[(u, v, m)]['inf_name'] # get interface
        sid = str(edge_labels[(u, v, m)]['adj_sid']) # get adjacency SID
        # Get edge labels
        u2v_edge_lbl = inf + ' : ' + sid
        v2u_edge_lbl = None
        if (v, u, snpa) in edge_labels:
            nei_inf = edge_labels[(v, u, snpa)]['inf_name'] # get neighbor interface
            nei_sid = str(edge_labels[(v, u, snpa)]['adj_sid']) # get neighbor adjacency SID
            v2u_edge_lbl = nei_inf + ' : ' + nei_sid

        # If True then we have bidirectional adjacency.
        if v2u_edge_lbl is not None:
            offset = 0.1
            connectionstyle = 'arc3,rad=0.2'
            if (u, v) in visited_pairs: # check if we have already drawn edges between the same nodes, then it means the second pair of interfaces in the game.
                if (v, u) in visited_pairs: # check if we have already drawn edges between the same nodes.
                    continue
                offset = 0.2
                connectionstyle = 'arc3,rad=0.3'
                dx = abs(pos[u][0] - pos[v][0]) * offset
                dy = abs(pos[u][1] - pos[v][1]) * offset
                mid = np.mean([pos[u], pos[v]], axis=0)
                u2v = mid - np.array([dx, dy])
                v2u = mid + np.array([dx, dy])
                # Draw additional edges (assuming not more than 2 point-to-point links between the same nodes)
                nx.draw_networkx_edges(net_DiGr, pos, edgelist=[(u, v)], width=1, style='dashed', connectionstyle=connectionstyle, edge_color='#FF33FF',
                                   arrowstyle=mpatches.ArrowStyle.CurveFilledB(head_length=.6, head_width=.4))
                nx.draw_networkx_edges(net_DiGr, pos, edgelist=[(v, u)], width=1, style='dashed', connectionstyle=connectionstyle, edge_color='#00CC00',
                                   arrowstyle=mpatches.ArrowStyle.CurveFilledB(head_length=.6, head_width=.4))
                # Draw additional labels
                ax.text(u2v[0], u2v[1], u2v_edge_lbl, horizontalalignment='center', verticalalignment='center', fontsize=10, color='#FF33FF')
                ax.text(v2u[0], v2u[1], v2u_edge_lbl, horizontalalignment='center', verticalalignment='center', fontsize=10, color='#00CC00') 
                visited_pairs.append((v, u))
                continue
            dx = abs(pos[u][0] - pos[v][0]) * offset
            dy = abs(pos[u][1] - pos[v][1]) * offset
            mid = np.mean([pos[u], pos[v]], axis=0)
            u2v = mid - np.array([dx, dy])
            v2u = mid + np.array([dx, dy])
            
            # Draw edges
            nx.draw_networkx_edges(net_DiGr, pos, edgelist=[(u, v)], width=1, style='dashed', connectionstyle=connectionstyle, edge_color='b',
                                   arrowstyle=mpatches.ArrowStyle.CurveFilledB(head_length=.6, head_width=.4))
            nx.draw_networkx_edges(net_DiGr, pos, edgelist=[(v, u)], width=1, style='dashed', connectionstyle=connectionstyle, edge_color='r',
                                   arrowstyle=mpatches.ArrowStyle.CurveFilledB(head_length=.6, head_width=.4))
            
            # Highlight edges for provided path.
            nx.draw_networkx_edges(net_DiGr, pos, edgelist=[(u, v)], width=1, edge_color='k', arrowstyle='-', label=None)
            
            # Draw labels
            ax.text(u2v[0], u2v[1], u2v_edge_lbl, horizontalalignment='center', verticalalignment='center', fontsize=10, color='b')
            ax.text(v2u[0], v2u[1], v2u_edge_lbl, horizontalalignment='center', verticalalignment='center', fontsize=10, color='r') 
            
            # Add edges to visited
            visited_adj.extend([(u, v, m), (v, u, snpa)])
            visited_pairs.append((u, v))
        else:
            dx = np.linspace(pos[u][0], pos[v][0], num=10)
            dy = np.linspace(pos[u][1], pos[v][1], num=10)
            mid = np.mean([pos[u], pos[v]], axis=0)
            u2v = mid + np.array[dx, dy]
            #print(f"u: {u}, v: {v}, mid_x: {mid}, u2v: {u2v}")
            # Draw labels
            ax.text(u2v[0], u2v[1], u2v_edge_lbl, horizontalalignment='center', verticalalignment='center', fontsize=10, color='k')
            
            # Add edges to visited
            visited_adj.append((u, v, m))
    
    if len(route) >= 2:
        # Highlight edges for provided path.
        for p in range(len(route) - 1):
            nx.draw_networkx_edges(net_DiGr, pos, edgelist=[(route[p], route[p+1])], width=2, edge_color='#00CC66', arrowstyle='-', label=None)


def get_inf_mac_by_adj(conn: Connection, node_adj: List[VEdge]) -> None:
    """Function gets MAC address of interface for each adjacency object.
    :parameter conn: Connection object.
    :type conn: Connection
    :parameter node_adj: List of adjacencies represented by VEdge.
    :type node_adj: VEdge
    :returns: None.
    :rtype: None
    """
    for e in node_adj:
        try:
            # Getting interface port.
            inf_port = conn.running.get(f'/nokia-conf:configure/router[router-name=Base]/interface[interface-name={e.inf_name}]/port', defaults=False).data
            
            # Normalise to leave only port.
            assert isinstance(inf_port, str)
            port: str = inf_port.split(':')[0]
            # Getting MAC address from /state.
            mac = conn.running.get(f'/nokia-state:state/port[port-id="{port}"]/hardware-mac-address', defaults=True).data
            
            # Normalise MAC address.
            assert isinstance(mac, str)
            mac = mac.replace(':', '').lower()
            mac = '0x' + mac
            e.inf_mac = mac
            
        except SrosMgmtError as mgmt_err:
            print(f"SROS management err: {mgmt_err}")
            sys.exit(201)
        except InvalidPathError as inv_path_err:
            print(f"Invalid path: {inv_path_err}")
            sys.exit(202)
    return None


def get_script_args() -> dict:
    """Function definition to get script arguments.
    :returns: Script arguments.
    :rtype: dict
    """
    import argparse
    parser = argparse.ArgumentParser(description='Draw ISIS SR domain graph.')
    parser.add_argument('-c', '--config', help='Configuration file name.', default='srgraph.yml')
    parser.add_argument('-y', '--yang', help='YANG models directory.', default='./7x50_YangModels/YANG')
    parser.add_argument('-n', '--nport', help='default NETCONF port.',  default=830)
    parser.add_argument('-u', '--user', help='default NETCONF username.', default='admin')
    parser.add_argument('-p', '--pwd', help='default NETCONF password.', default='admin')
    parser.add_argument('-a', '--adjmatrix', action="store_true", help='Adjacency matrix.')
    parser.add_argument('-g', '--graph', action="store_true", help='Draw Graph.')
    parser.add_argument('-s', '--src', help='Source node.')
    parser.add_argument('-d', '--dst', help='Destination node.')
    
    # Parsing arguments.
    args = parser.parse_args()
    
    return {'config': args.config, 'yang': args.yang, 'port': args.nport, 'user': args.user, 'pwd': args.pwd,
            'adjmatrix': args.adjmatrix, 'graph': args.graph, 'src': args.src, 'dst': args.dst}


def main():
    if sros():
        print("Not supported!")
        exit(0)
    
    # Getting script arguments.
    f = get_script_args()
    
    # Loading configuration.
    config = load_config(filename=f['config'])
    root = config['root']
    
    # Connection parameters and defaults.
    yang_dir = config['yang_path'] if "yang_path" in config else f['yang']
    user = root['user'] if 'user' in root else f['user']
    pwd = root['pwd'] if 'pwd' in root  else f['pwd']
    port = root['netconf_port'] if 'netconf_port' in root else f['port']
    
    # Getting to the first node.
    root_conn: Connection = get_connection(host=root['host'], user=user, pwd=pwd, y_dir=yang_dir, port=port)
    
    # ISIS state.
    isis_0: Container
    
    # SRGB configuration.
    srgb: Container
    try:
        isis_0 = root_conn.running.get('/nokia-state:state/router[router-name="Base"]/isis[isis-instance="0"]',
                                defaults=True)
        srgb = root_conn.running.get('/configure/router[router-name=Base]/mpls-labels/sr-labels', defaults=True)
    except SrosMgmtError as mgmt_err:
        print(f"SROS management err: {mgmt_err}")
        sys.exit(1)
    except InvalidPathError as inv_path_err:
        print(f"Invalid path: {inv_path_err}")
        sys.exit(2)
    
    # Debugging data structure.
    # pprint("###ALL ROOT DATA###")
    # pprint(isis_0.data, indent=4, width=80, depth=6)
    
    # Creating list of the nodes. Assuming we have one ISIS instance and one L2 area.
    nodes: List[VNode] = []
    srgb_start = 0
    for id in isis_0.data['hostname']:
        nodes.append(VNode(isis_0.data['hostname'][id].data['host-name'].data, id))
    
    # Eliciting SRGB start, assuming we have one SRGB for whole domain and not useing indexing.
    if 'start' in srgb.data:
        srgb_start = srgb.data['start'].data
    else:
        print("Can't identify SRGB start from configuration. Exiting.")
        exit(3)
    
    # Identifying Node-SIDs out fo Prefix-SIDs
    for p_sid in isis_0.data['prefix-sid']:
        d_e = isis_0.data['prefix-sid'][p_sid].data
        if 'bit-n' in isis_0.data['prefix-sid'][p_sid].data['flags'].data:
            system_id = d_e['advertising-system-id'].data
            for node in nodes:
                if node.system_id == system_id:
                    node.nsid = srgb_start + d_e['label'] # calculating Node-SID, since label is index
    
    # System ID of the current node (operational).
    node_id = isis_0.data['oper-system-id'].data
    
    # Adding adjacencies, assuming we have one ISIS instance and one L2 area.
    # Assuming we have not more then one adjcenecy per interface.
    # Assuming we have not more than two point-to-point link between the same nodes.
    adj_martix = [[None] * len(nodes) for _ in range(len(nodes))]  # adjacency matrix, filled in with None (not using numpy to make it simple), but will be replaced with VEdge.
    
    # Iterating over all infs and adjacencies
    all_adjs: List[VEdge] = get_inf_adjs(isis_0, nodes, adj_martix)
    
    # Getting interface MAC addresses from the state for ISIS interfaces.
    get_inf_mac_by_adj(root_conn, all_adjs)
    
    # Iterate over other nodes and get adjacencies and fill in adjacency matrix with labels
    for node in config['nodes']:
        isis: Container
        n_conn: Connection
        
        # Connection parameters and defaults.
        yang_dir = config['yang_path'] if "yang_path" in config else f['yang']
        user = node['user'] if 'user' in node else f['user']
        pwd = node['pwd'] if 'pwd' in node else f['pwd']
        port = node['netconf_port'] if 'netconf_port' in node else f['port']
        
        n_conn = get_connection(host=node['host'], user=user, pwd=pwd, y_dir=yang_dir, port=port)
        
        try:
            isis = n_conn.running.get('/nokia-state:state/router[router-name="Base"]/isis[isis-instance="0"]',
                                defaults=True)
        except SrosMgmtError as mgmt_err:
            print(f"SROS management err: {mgmt_err}")
            sys.exit(11)
        except InvalidPathError as inv_path_err:
            print(f"Invalid path: {inv_path_err}")
            sys.exit(12)

        # Adding adjacencies, assuming we have one ISIS instance and one L2 area.
        node_adjs = get_inf_adjs(isis, nodes, adj_martix)
        
        # Getting interface MAC addresses from the state for ISIS interfaces.
        get_inf_mac_by_adj(n_conn, node_adjs)
        
        # Extend list of adjacencies with adjacencies from the node.
        all_adjs.extend(node_adjs)

    
    # Print adjacency matrix.
    if f['adjmatrix']:
        print("Adjacency matrix:")
        for row in adj_martix:
            for col in row:
                if col is None:
                    print(f"{'':40}", end='| ')
                else:
                    print(f"{str(col):<40}", end='| ')
            print('\n')

    # Creating a graph.
    net_gr = nx.MultiDiGraph()
    net_gr.add_nodes_from([n.nx_node for n in nodes])
    net_gr.add_edges_from([e.nx_edge for e in all_adjs])
    
    # SFP calculation for src -> dst.
    spf_nodes = []
    if f['src'] is not None and f['dst'] is not None:
        src_idx = name_to_idx(nodes, f['src'])
        dst_idx = name_to_idx(nodes, f['dst'])
        
        if src_idx != -1 and dst_idx != -1:
            spf_nodes = nx.shortest_path(net_gr, nodes[src_idx], nodes[dst_idx], method='dijkstra')
            print(f"Path from {nodes[src_idx]} to {nodes[dst_idx]}: {spf_nodes}")
        else:
            print(f"Source or destination node not found. Skipping SPF.")
    
    # Drawing a graph.
    if  f['graph']:
         
        seed = 981509  # Seed random number generators for reproducibility
        pos = nx.spring_layout(net_gr, seed=seed)
        
        subax1 = plt.subplot(111)
        subax1.set_title("ISIS SR domain", fontsize=16)
        spf_set = set(spf_nodes)
        non_sfp_set = set(net_gr.nodes) - spf_set
        nx.draw_networkx_nodes(net_gr, pos, node_size =500, nodelist=spf_nodes, node_color='#00CC66', edgecolors='w', linewidths=2)
        
        nx.draw_networkx_nodes(net_gr, pos, node_size =500, nodelist=list(non_sfp_set), node_color='#CCE5FF', edgecolors='w', linewidths=2)
        
        nx.draw_networkx_labels(net_gr, pos, font_weight='bold', font_size=10, font_color='k')
        
        # Draw edges and edge labels in respect to adjacency SID (edge label) and adjacency direction combination.
        draw_edges(net_gr, pos, subax1, spf_nodes)
        plt.show()
    
    exit(0)


# Entry point.
if __name__ == '__main__':
    main()
