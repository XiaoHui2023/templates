from typeguard import typechecked
from typing import List, Optional
from .base import Base
from .reg import Reg
import math

@typechecked
class Block(Base):
    def __init__(
        self,
        class_name: str,
        reg_model_class_name: str,
        regs: list,
        name: str = "",
        reg_model_name: str = "",
        blocks: Optional[List] = None,
        extend: str = "uvm_sequence_item",
        depth: int = 1,
        **kwargs,
    ):
        """
        Args:
            name : 实例名
            class_name : 类名
            regs :
            blocks :
            depth : 深度
        """
        if blocks is None:
            blocks = []
        super().__init__(**kwargs)

        self.name = name
        self.class_name = class_name
        self.regs = [self.new_reg(**r) for r in regs]
        self.blocks = [self.new_block(**x) for x in blocks]
        self.reg_model_name = reg_model_name
        self.reg_model_class_name = reg_model_class_name
        self.extend = extend
        self.depth = depth

        self.max_class_name_length = 0

    def new_reg(self, **kwargs) -> "Reg":
        return self.new_object(Reg,
            class_prefix=f"{self.class_name}_",
            **kwargs,
        )

    def new_block(self, **kwargs) -> "Block":
        return self.new_object(Block, **kwargs)

    def render(self):
        """
        渲染
        """
        super().render()

        self.max_class_name_length = self._get_max_class_name_length()

    def _get_max_class_name_length(self) -> int:
        """
        得到reg中最长类名的长度
        """
        return max([len(x.class_name) for x in self.regs + self.blocks])

    def format_class_name(self, name: str) -> str:
        """
        格式化reg类名长度和当前最长状态以保持比较好的对齐
        """
        max_len = self.max_class_name_length
        l = math.floor(max_len / 4) + 1
        return name.ljust(l * 4)
