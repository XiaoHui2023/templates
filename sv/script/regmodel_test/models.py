from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_name: str = Field(
        "reg_test_register_test_seq",
        min_length=1,
        description="该 sequence 的类名。",
    )
    hw_reset: bool = Field(False, description="启用 `uvm_reg_hw_reset_seq`。")
    access: bool = Field(False, description="启用 `uvm_reg_access_seq`。")
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
