from pydantic import BaseModel

class Context(BaseModel):
    class_name: str
