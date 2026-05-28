import re
import math
from pydantic import BaseModel, Field, computed_field
from typing import List, Literal


class Metadata(BaseModel):
    name: str
    address: int
    nibble: Literal['high', 'low', 'all']
    width: int
    type: str

    @computed_field
    def name_legal(self) -> str:
        replace_map = {
            r"^\d(.*?)": r"_\1",  # 非法开头
            r"[\s\W]": r"_",  # 标点符号
        }
        name = self.name.strip().lower()

        for pattern, repl in replace_map.items():
            name = re.sub(pattern, repl, name)
        return name

    @computed_field
    def address_hex(self) -> str:
        return hex(self.address).replace('0x', "'h")

    @computed_field
    def nibble_upper(self) -> str:
        return self.nibble.upper()

    @computed_field
    def bytes(self) -> int:
        return math.ceil(self.width / 8)


class Models(BaseModel):
    class_prefix: str = Field('otp', description="类名前缀")
    class_map: str = Field('', description="map类名")
    class_manifest: str = Field('', description="manifest类名")
    class_entry: str = Field('', description="entry类名")
    class_ini_io: str = Field('', description="ini_io类名")
    entries: List[Metadata] = Field(..., description="条目列表")

    max_width: int = Field(0, description="最大位宽，默认等于最宽的数据的位宽")
    WAIT_READY_TIMEOUT_MS: int = Field(10, description="wait_ready的timeout_ms参数默认值")
    WAIT_READY_TIMEOUT_US: int = Field(0, description="wait_ready的timeout_us参数默认值")
    types: List[str] = []

    def model_post_init(self, ctx):
        if not self.class_map:
            self.class_map = f"{self.class_prefix}map"
        if not self.class_manifest:
            self.class_manifest = f"{self.class_prefix}manifest"
        if not self.class_entry:
            self.class_entry = f"{self.class_prefix}entry"
        if not self.class_ini_io:
            self.class_ini_io = f"{self.class_prefix}ini_io"
        if self.max_width <= 0:
            self.max_width = max([x.width for x in self.entries])
        self.types = list(set([x.type for x in self.entries]))
