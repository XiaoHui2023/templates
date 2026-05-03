from typeguard import typechecked
from typing import Tuple
from .base import Base

@typechecked
class Variable(Base):
    def __init__(
        self,
        name: str,
        msb: int,
        lsb: int,
        is_rand: bool = False,
        is_protected: bool = False,
        **kwargs,
    ):
        """
        Args:
            name : 名字
            msb : 最高位
            lsb : 最低位
            is_rand : 是否是rand变量
            is_protected : 是否protected变量
        """
        super().__init__(**kwargs)
        self.name = name.lower()
        self.lsb = lsb
        self.msb = msb
        self.is_rand = is_rand
        self.is_protected = is_protected

    @property
    def range(self) -> Tuple[int, int]:
        return (self.lsb, self.msb)

    @property
    def width(self) -> int:
        return self.msb - self.lsb + 1
