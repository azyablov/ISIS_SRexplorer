import uuid
from abc import ABC, abstractmethod, ABCMeta
from typing import List, TypeVar, Generic, List, Dict, Tuple


class Vertex(metaclass=ABCMeta):
    def __init__(self):
        pass

    @property
    @abstractmethod
    def uuid(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self):
        raise NotImplementedError

class Edge(metaclass=ABCMeta):
    def __init__(self, v1: Vertex, v2: Vertex):
        pass

    @property
    @abstractmethod
    def uuid(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def vertices(self):
        raise NotImplementedError
    
    
class VNode(Vertex):
    def __init__(self, name: str, system_id: str):
        super().__init__()
        assert isinstance(name, str)
        self._name = name
        self._uuid = uuid.uuid4()
        self._nsid = 0
        self._system_id = system_id

    def __repr__(self):
        return f'<Name: {self._name}, SystemID: {self._system_id}>'
    
    def __str__(self) -> str:
        return f"{self._name} ({self.nsid})"
    
    def __hash__(self) -> int:
        return hash(self._uuid)
    
    def __eq__(self, o: object) -> bool:
        if isinstance(o, VNode):
            return self._uuid == o.uuid and self._system_id == o._system_id
        return False

    @property
    def uuid(self):
        return self._uuid

    @property
    def name(self):
        return self._name
    
    @property
    def nsid(self):
        return self._nsid
    
    @nsid.setter
    def nsid(self, value: int):
        assert isinstance(value, int)
        self._nsid = value
        
    @property
    def system_id(self):
        return self._system_id
    
    @system_id.setter
    def system_id(self, value: str):
        assert isinstance(value, str)
        self._system_id = value
        
    @property
    def nx_node(self):
        return (self, {"nsid": self._nsid, "system_id": self._system_id})
    
    
class VEdge(Edge):
    def __init__(self, v1: VNode, v2: VNode, adj_sid: int = 0):
        super().__init__(v1, v2)
        self._uuid = uuid.uuid4()
        self._vertices = [v1, v2]
        self.adj_sid = adj_sid
        self._inf_name = "" # Optional, to record interface name.
        self._nei_snpa = "" # Optional, needed in case of muliple point-to-point links between the same nodes.

    def __str__(self):
        return f'{self._vertices[0]} -> {self._vertices[1]}: {self.adj_sid}'
    
    def __repr__(self):
        return f'<Vertices: {[str(v) for v in self._vertices]}, UUID: {self._uuid}>'

    @property
    def uuid(self):
        return self._uuid

    @property
    def vertices(self):
        return self._vertices
    
    @property
    def nx_edge(self):
        return (self._vertices[0], self._vertices[1], 
                {"adj_sid": self.adj_sid, "inf_name": self.inf_name, 
                 "inf_mac": self.inf_mac, "nei_snpa": self.nei_snpa})
    
    @property
    def adj_sid(self):
        return self._adj_sid

    @adj_sid.setter
    def adj_sid(self, value: int):
        assert isinstance(value, int)
        self._adj_sid = value
    
    @property
    def inf_name(self):
        return self._inf_name
    
    @inf_name.setter
    def inf_name(self, value: str):
        assert isinstance(value, str)
        self._inf_name = value
        
    @property
    def nei_snpa(self):
        return self._nei_snpa
    
    @nei_snpa.setter
    def nei_snpa(self, value: str):
        assert isinstance(value, str)
        self._nei_snpa = value
    
    @property
    def inf_mac(self):
        return self._inf_mac
    
    @inf_mac.setter
    def inf_mac(self, value: str):
        assert isinstance(value, str)
        assert len(value) == 14
        assert value.startswith('0x')
        self._inf_mac = value
        