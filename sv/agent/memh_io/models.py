from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field("memh_", description="默认类名的前缀")
    input_port_name: str = Field("i_ap", description="输入 payload 的 analysis port 名字")
    output_port_name: str = Field("o_load_ap", description="输出文件加载 payload 的 analysis port 名字")
    memh_max_bytes_per_line: int = Field(
        16,
        ge=1,
        description="写出 memh 时每行最多包含的连续数据字节数。",
    )
