from typeguard import typechecked
from typing import List, Union, Tuple
from .variable import Variable

@typechecked
class Field(Variable):
    def __init__(
        self,
        is_nopack: bool = False,
        is_noprint: bool = False,
        is_reserved: bool = False,
        access: str = "",
        **kwargs,
    ):
        """
        Args:
            access : 读写方式
            is_nopack : 是否不打包
            is_noprint : 是否不打印
            is_reserved : 是否为保留输出，去实际作用
        """
        super().__init__(**kwargs)
        self.access = access
        self.is_nopack = is_nopack
        self.is_noprint = is_noprint
        self.is_reserved = is_reserved

    @property
    def is_writable(self) -> bool:
        """
        是否可写
        """
        return self.access in [
            "rw",
            "wo",
            "w1_a",
        ]

    @property
    def options(self) -> List[str]:
        """
        选项列表
        """
        rt = ["UVM_ALL_ON"]
        if self.is_nopack:
            rt.append("UVM_NOPACK")
        if self.is_noprint:
            rt.append("UVM_NOPRINT")
        return rt

    @property
    def option(self) -> str:
        """
        选项文本
        """
        return " | ".join(self.options)

    @property
    def range(self) -> Union[Tuple[int], Tuple[int, int]]:
        if self.lsb == self.msb:
            return (self.lsb,)
        else:
            return (self.msb, self.lsb)

    @property
    def type(self) -> str:
        """
        bit类型中间出现多bit填充一段
        不连续写两行宏范围中间不用声明中间bit时就不能用0开始就要多算一个lsb
        """
        if self.msb == 0 and self.lsb == 0:
            return "bit"
        return f"bit[{self.msb}:{self.lsb}]"
