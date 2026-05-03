from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_prefix: str = Field('', description="默认类名前缀")
    class_scoreboard: str = Field('', description="scoreboard类名")
    class_table: str = Field('', description="table类名")
    class_handler: str = Field('', description="handler类名")
    class_package: str = Field('', description="package类名")

    class_data: str = Field(..., description="输入数据类型名")
    data_type: str = Field('', description="数据类型名")

    gld_port_name: str = Field('gld_ap', description="golden端口名字")
    mon_port_name: str = Field('mon_ap', description="monitor端口名字")

    @model_validator(mode='after')
    def _post_init(self):
        if not self.class_scoreboard:
            self.class_scoreboard = f"{self.class_prefix}atom_scoreboard"
        if not self.class_table:
            self.class_table = f"{self.class_scoreboard}_table"
        if not self.class_handler:
            self.class_handler = f"{self.class_scoreboard}_handler"
        if not self.class_package:
            self.class_package = f"{self.class_scoreboard}_package"
        if not self.data_type:
            self.data_type = self.class_data

        return self
