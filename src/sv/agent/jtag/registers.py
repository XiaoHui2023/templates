from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Register(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: int = Field(0, ge=0, description="IR 指令值")
    length: int = Field(32, ge=1, description="DR 位数")
    access: Literal["read", "write", "read_write"] = Field("read", description="读写权限")
    value: int = Field(0, ge=0, description="扫描时从 TDI 发送的值")
    expected: int = Field(0, ge=0, description="TDO 期望值")
    check_mask: int = Field(0, ge=0, description="置 1 的位参与比较，0 表示不检查")
