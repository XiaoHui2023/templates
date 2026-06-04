from pydantic import BaseModel, ConfigDict, Field, model_validator


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field(
        "ral_test_",
        min_length=1,
        description="生成类型名所用前缀；主 sequence 为此前缀加 seq，reg_fd 辅助 sequence 的类型名亦带此前缀。",
    )
    reset: bool = Field(
        False,
        description="启用寄存器复位默认值自测：仅前门读并与 RAL 复位值核对，不依赖后门或 HDL 路径。",
    )
    access: bool = Field(
        False,
        description=(
            "启用寄存器访问自测：按 field 翻转可写位、前门写读与镜像核对；"
            "每个 field 测完立刻写回测前读到的整寄存器值，再测下一个 field；不依赖后门或 HDL 路径。"
        ),
    )
    mem_hdl_paths: bool = Field(
        False, description="启用 `uvm_reg_mem_hdl_paths_seq`。"
    )
    bit_bash: bool = Field(False, description="启用 `uvm_reg_bit_bash_seq`。")
    ignore_partial_ro_fields: bool = Field(
        False,
        description=(
            "为真时，对仍含可写字段的寄存器，在 map 上访问类型为 RO 的 field "
            "写入 uvm_resource_db 的 NO_FIELD_TESTS；前门 reset 与 access 自测均不核对被标记 "
            "field，且 access 每次只翻转当前 field 的可写位。"
        ),
    )

    @model_validator(mode="after")
    def at_least_one_test(self):
        if not (
            self.reset
            or self.access
            or self.mem_hdl_paths
            or self.bit_bash
        ):
            raise ValueError(
                "须至少启用 reset、access、mem_hdl_paths、bit_bash 之一。"
            )
        return self
