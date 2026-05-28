from typing_extensions import override
from typeguard import typechecked
from typing import Optional, Union, Dict, Any, Type, List
from .context import Context

@typechecked
class Base:
    def __init__(
        self,
        parent: Optional["Base"] = None,
        ctx: Optional[Union["Context", Dict[str, Any]]] = None,
    ):
        self.parent = parent

        if ctx:
            self.ctx = ctx if isinstance(ctx, Context) else Context(**ctx)
        else:
            self.ctx = parent.ctx if parent else None
        self.children: List["Base"] = []

    @override
    def render(self):
        """
        渲染
        """
        for child in self.children:
            child.render()

    def new_object(self, T: Type["Base"], obj: Optional["Base"] = None, **kwargs) -> "Base":
        """
        新建对象
        """
        if obj is None:
            obj = T(parent=self, **kwargs)
        self.children.append(obj)
        return obj
