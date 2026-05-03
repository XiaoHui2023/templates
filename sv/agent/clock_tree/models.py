from pydantic import BaseModel, Field, model_validator
from typing import List, Union, Literal, Optional


class Reg(BaseModel):
    path: str = Field(..., description="相对于regmodel的寄存器路径")
    lsb: int = Field(..., description="低位")
    width: int = Field(..., description="位宽")


class BaseCell(BaseModel):
    name: str = Field(..., description="名字")
    is_array: bool = Field(False, description="是否是数组")
    array_size: int = Field(0, description="数组大小")

    def __getitem__(self, item):
        return getattr(self, item)


class Div(BaseCell):
    type: Literal["div"] = "div"
    reg_rstn: Reg = Field(..., description="rstn寄存器")
    reg_load_en: Reg = Field(..., description="load_en寄存器")
    reg_bypass: Optional[Reg] = Field(None, description="bypass寄存器")
    reg_step: Reg = Field(..., description="step寄存器")
    regs_name: List[str] = [
        "reg_rstn",
        "reg_load_en",
        "reg_step",
    ]

    @model_validator(mode="after")
    def __post_init(self):
        if self.reg_bypass:
            self.regs_name.append("reg_bypass")
        return self


class Sel(BaseCell):
    type: Literal["sel"] = "sel"
    reg_sel: Reg = Field(..., description="寄存器")
    regs_name: List[str] = ["reg_sel"]


class Gate(BaseCell):
    type: Literal["gate"] = "gate"
    reg_gate: Reg = Field(..., description="寄存器")
    regs_name: List[str] = ["reg_gate"]


class Inv(BaseCell):
    type: Literal["inv"] = "inv"
    reg_inv: Reg = Field(..., description="寄存器")
    regs_name: List[str] = ["reg_inv"]


CELL_UNION = Union[Sel, Gate, Inv, Div]


class Models(BaseModel):
    cells: List[CELL_UNION] = Field(..., description="单元列表")
    class_regmodel: str = Field(..., description="寄存器模型类名")
    name_regmodel: str = Field("regmodel", description="寄存器实例名")
    class_tree: str = Field(..., description="tree类名")
    class_base_cell: str = Field("", description="base cell类名")
    class_div: str = Field("", description="div类名")
    class_inv: str = Field("", description="inv类名")
    class_sel: str = Field("", description="sel类名")
    class_gate: str = Field("", description="gate类名")
    class_reg: str = Field("", description="reg类名")
    name_constraint_default: str = Field("cst_default", description="默认约束名字")
    name_constraint_user: str = Field("cst_user", description="用户约束名字")
    name_on_main: str = Field("main", description="main回调函数名字")

    model_config = {
        "discriminator": "type"
    }

    @model_validator(mode="after")
    def __post_init(self):
        if not self.class_base_cell:
            self.class_base_cell = f"{self.class_tree}_base_cell"
        if not self.class_div:
            self.class_div = f"{self.class_tree}_div"
        if not self.class_inv:
            self.class_inv = f"{self.class_tree}_inv"
        if not self.class_sel:
            self.class_sel = f"{self.class_tree}_sel"
        if not self.class_gate:
            self.class_gate = f"{self.class_tree}_gate"
        if not self.class_reg:
            self.class_reg = f"{self.class_tree}_reg"
        return self

    def cell_to_class_name(self, cell: CELL_UNION) -> str:
        """根据cell类型获取类名"""
        if isinstance(cell, Sel):
            return self.class_sel
        elif isinstance(cell, Gate):
            return self.class_gate
        elif isinstance(cell, Inv):
            return self.class_inv
        elif isinstance(cell, Div):
            return self.class_div
