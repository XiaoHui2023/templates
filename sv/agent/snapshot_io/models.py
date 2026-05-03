from typing import List

from pydantic import BaseModel, Field, model_validator


class Data(BaseModel):
    name: str = Field(..., description="数据的名字")
    port_name: str = Field("", description="输入数据端口名字")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.port_name:
            self.port_name = f"{self.name}_op"
        return self


class Models(BaseModel):
    class_prefix: str = Field(..., description="默认类名的前缀")
    class_component: str = Field("", description="组件类名")
    class_core: str = Field("", description="core组件类名")
    class_data: str = Field("", description="data类名")
    on_check_name: str = Field("on_check", description="检查回调函数名字")
    func_snapshot_name: str = Field("snapshot", description="snapshot函数名字")
    func_get_name: str = Field("get", description="get函数名字")
    func_get_by_reset_name: str = Field("", description="get_by_reset函数名字")
    func_get_by_net_name: str = Field("", description="get_by_net函数名字")
    func_clear_name: str = Field("clear", description="clear函数名字")
    func_compare_name: str = Field("compare_with", description="compare函数名字")
    datas: List[Data] = Field(..., description="数据列表")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.class_component:
            self.class_component = f"{self.class_prefix}snapshot"
        if not self.class_core:
            self.class_core = f"{self.class_component}_core"
        if not self.class_data:
            self.class_data = f"{self.class_component}_data"
        if not self.func_get_by_reset_name:
            self.func_get_by_reset_name = f"{self.func_get_name}_by_reset"
        if not self.func_get_by_net_name:
            self.func_get_by_net_name = f"{self.func_get_name}_by_net"
        return self
