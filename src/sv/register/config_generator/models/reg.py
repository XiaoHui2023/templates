from typeguard import typechecked
from typing import List
from .base import Base
from .field import Field

@typechecked
class Reg(Base):
    def __init__(
        self,
        class_prefix: str,
        name: str,
        reg_model_name: str,
        fields: List,
        reset_value: int,
        **kwargs,
    ):
        """
        Args:
            reg model name: 寄存器模型名字
            name: 寄存器名
            class_prefix: 类名前缀
            reset_value: 复位值
        Attributes:
            class_name: 类名
        """
        super().__init__(**kwargs)
        self.reg_model_name = reg_model_name
        self.name = name
        self.fields = [self.new_field(**v, is_rand=True) for v in fields]
        self.reset_value = f"h{reset_value:x}"

        self.class_name = f"{class_prefix}{self.name}"

    def new_field(self, **kwargs) -> "Field":
        return self.new_object(Field, **kwargs)

    def fields_order(self, little_endian: bool = False) -> List["Field"]:
        """
        将fields按大小排序
        little endian : 是否小端
        """
        return sorted(self.fields, key=lambda x: x.lsb, reverse=not little_endian)

    def _insert_reserved(self, fields: List["Field"]) -> List["Field"]:
        """
        在空的位置插入reserved域
        """
        # 跳过已有NOPRINT
        ranges_map = {(x.lsb, x.msb): x for x in fields}
        missing = find_missing_ranges(list(ranges_map.keys()))
        missing_map = {f"slv_res_reserved{v}" for v in missing}
        return merge_dicts_by_range(ranges_map, missing_map)

    def _new_reserved(self, lsb: int, msb: int) -> "Field":
        """
        新建reserved域
        """
        if msb == lsb:
            lsb = (lsb,)
        else:
            r = (msb, lsb)

        lo = "_".join([str(x) for x in r])
        name = f"reserved_{lo}"
        return Field(
            name=name,
            lsb=lsb,
            msb=msb,
            is_noprint=True,
            is_rand=False,
            is_protected=True,
            is_reserved=True,
            parent=self,
        )

    @property
    def msb(self) -> int:
        """
        最高有效位
        """
        return max([field.msb for field in self.fields if not field.is_reserved])

    @property
    def value_type(self) -> str:
        """
        value变量类型
        """
        if self.msb == 0:
            return "bit"
        else:
            return f"bit[{self.msb}:0]"

def find_missing_ranges(ranges, total_start=0, total_end=31):
    """
    ranges: 已有的范围，如 [(start, end), ...]
    total_start, total_end: 总范围
    返回：缺失的区间列表
    """
    # 按起始排序
    ranges = sorted(ranges, key=lambda x: x[0])

    missing = []
    current = total_start

    for start, end in ranges:
        if start > current:
            missing.append((current, start - 1))
        current = max(current, end + 1)

    # 最后检查范围
    if current <= total_end:
        missing.append((current, total_end))

    return missing


def merge_dicts_by_range(*dicts):
    """
    根据多个 dict[key 为 (start, end)] 的value 为元素
    按照范围将元素的 value 排序
    """
    items = []
    for d in dicts:
        items.extend(d.items())
    # 按照起点排序
    items.sort(key=lambda x: x[0][0])
    return [v for _, v in items]
