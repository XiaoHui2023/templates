from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    """
    # register_test 脚本模板

    用于在已接好的寄存器模型与总线访问路径上，按开关选择并运行 UVM 自带的若干寄存器测试 sequence。

    # Usage

    在测试环境中为本 sequence 提供寄存器模型根（`uvm_reg_block`），将该模型上的默认 map 与总线侧 sequencer、adapter 按项目惯例关联后，再启动本 sequence。至少须启用硬件复位、存储器 HDL 路径、位翻转三类内建测试之一。若要对个别寄存器跳过自带测试，请在测试环境中按您项目对 UVM 寄存器测试的惯例自行处理。
    """

    class_name: str = Field(
        "reg_test_register_test_seq",
        min_length=1,
        description="该 sequence 的类名。",
    )
    hw_reset: bool = Field(False, description="启用 `uvm_reg_hw_reset_seq`。")
    mem_hdl_paths: bool = Field(
        False, description="启用 `uvm_reg_mem_hdl_paths_seq`。"
    )
    bit_bash: bool = Field(False, description="启用 `uvm_reg_bit_bash_seq`。")

    @model_validator(mode="after")
    def at_least_one_builtin(self):
        if not (self.hw_reset or self.mem_hdl_paths or self.bit_bash):
            raise ValueError("须至少启用 hw_reset、mem_hdl_paths、bit_bash 之一。")
        return self
