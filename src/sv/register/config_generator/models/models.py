from typeguard import typechecked
from typing import List
from .block import Block
from .reg import Reg
from .base import Base

@typechecked
class Models(Base):
    def __init__(
        self,
        block: dict,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.block = self.new_block(**block)

    def new_block(self, **kwargs) -> "Block":
        return self.new_object(Block, **kwargs)
