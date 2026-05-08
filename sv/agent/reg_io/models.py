from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field("reg_io_", description="生成类名前缀（须非空）")
    input_port_name: str = Field("i_ap", description="外部写事务 analysis port 名")
    output_port_name: str = Field("o_ap", description="CSV 加载写事务输出的 analysis port 名")
