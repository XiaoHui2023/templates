from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_prefix: str = Field(
        "ral_test_",
        min_length=1,
        description="生成类型名所用前缀；主 sequence 为此前缀加 seq，reg_fd 辅助 sequence 的类型名亦带此前缀。",
    )
    hw_reset: bool = Field(False, description="启用 `uvm_reg_hw_reset_seq`。")
    access: bool = Field(
        False,
        description="启用寄存器访问自测：前门写读与镜像核对，不依赖后门或 HDL 路径。",
    )
    mem_hdl_paths: bool = Field(
        False, description="启用 `uvm_reg_mem_hdl_paths_seq`。"
    )
    bit_bash: bool = Field(False, description="启用 `uvm_reg_bit_bash_seq`。")

    @model_validator(mode="after")
    def at_least_one_builtin(self):
        if not (
            self.hw_reset
            or self.access
            or self.mem_hdl_paths
            or self.bit_bash
        ):
            raise ValueError(
                "须至少启用 hw_reset、access、mem_hdl_paths、bit_bash 之一。"
            )
        return self
