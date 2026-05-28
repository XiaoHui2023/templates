from typing import List
from models import Block, Reg
from dataclasses import dataclass

@dataclass
class Template:
    class_name: str
    block: Block
    regs: List[Reg]
    groups: List[Block]
    has_stream: bool
    has_sync: bool
    has_pack: bool
    has_virtual_field: bool
    virtual_field_class_name: str
    virtual_int_class_name: str
    virtual_bit_class_name: str
