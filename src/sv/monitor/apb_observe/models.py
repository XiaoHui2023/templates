from typing import List
from pydantic import BaseModel, Field


class InfoStore(BaseModel):
    catch: bool = Field(False, description="是否在sequencer中存储事务")
    to_write_value: bool = Field(False, description="是否在sequencer中存储写数据")
    to_read_value: bool = Field(False, description="是否在sequencer中存储读数据")
    to_value: bool = Field(False, description="是否在sequencer中存储数据")
    read_fifo: bool = Field(False, description="是否在sequencer中存储读FIFO")
    write_fifo: bool = Field(False, description="是否在sequencer中存储写FIFO")
    to_write_fifo: bool = Field(False, description="是否在sequencer中存储写FIFOR")
    to_read_fifo: bool = Field(False, description="是否在sequencer中存储读FIFOR")

    def model_post_init(self, ctx):
        # 若没有启用任何存储项，默认开启 catch。
        if not any([
            self.catch,
            self.to_write_value,
            self.to_read_value,
            self.to_value,
            self.read_fifo,
            self.write_fifo,
            self.to_write_fifo,
            self.to_read_fifo,
        ]):
            self.catch = True


class Models(BaseModel):
    class_prefix: str = Field('apb_observe', description="类名前缀")
    info_store: InfoStore = Field(default_factory=InfoStore)
    is_emu: bool = Field(False, description="是否为硬件仿真")

    def model_post_init(self, ctx):
        pass
