from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field(
        "memh_io_",
        description="生成类名的前缀，与族内后缀直接拼接；建议含末尾下划线。默认得到 memh_io_engine、memh_io_callback 等。",
    )
    input_port_name: str = Field("i_ap", description="输入 payload 的 analysis port 名字")
    output_port_name: str = Field("o_load_ap", description="输出文件加载 payload 的 analysis port 名字")
    memh_max_bytes_per_line: int = Field(
        16,
        ge=1,
        description="写出 memh 时每行最多包含的连续数据字节数。",
    )
