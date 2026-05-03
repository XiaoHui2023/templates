from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_prefix: str = Field(..., description="????")
    class_scoreboard: str = Field('', description="scoreboard????")
    class_math: str = Field('', description="math????")
    class_comparator: str = Field('', description="comparator????")
    class_compressor: str = Field('', description="compressor????")
    class_formatter: str = Field('', description="formatter????")
    class_reporter: str = Field('', description="reporter????")
    class_block: str = Field('', description="block????")
    class_column: str = Field('', description="column????")
    class_row: str = Field('', description="row????")
    class_table: str = Field('', description="table????")
    class_transfer: str = Field('', description="transfer????")
    class_sheet: str = Field('', description="sheet????")
    define_array_imp_decl: str = Field('', description="imp???????")

    golden_port_name: str = Field('gld_ap', description="golden???")
    monitor_port_name: str = Field('mon_ap', description="monitor???")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.class_scoreboard:
            self.class_scoreboard = f"{self.class_prefix}graph_search_scoreboard"
        if not self.class_math:
            self.class_math = f"{self.class_scoreboard}_math"
        if not self.class_comparator:
            self.class_comparator = f"{self.class_scoreboard}_comparator"
        if not self.class_compressor:
            self.class_compressor = f"{self.class_scoreboard}_compressor"
        if not self.class_formatter:
            self.class_formatter = f"{self.class_scoreboard}_formatter"
        if not self.class_reporter:
            self.class_reporter = f"{self.class_scoreboard}_reporter"
        if not self.class_block:
            self.class_block = f"{self.class_scoreboard}_block"
        if not self.class_column:
            self.class_column = f"{self.class_scoreboard}_column"
        if not self.class_row:
            self.class_row = f"{self.class_scoreboard}_row"
        if not self.class_table:
            self.class_table = f"{self.class_scoreboard}_table"
        if not self.class_transfer:
            self.class_transfer = f"{self.class_scoreboard}_transfer"
        if not self.class_sheet:
            self.class_sheet = f"{self.class_scoreboard}_sheet"
        if not self.define_array_imp_decl:
            self.define_array_imp_decl = f"{self.class_scoreboard}_array_imp_decl"
        return self
