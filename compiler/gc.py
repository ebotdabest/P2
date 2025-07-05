from llvmlite import ir
from typing import List

class HeapObject:
    def __init__(self, tpe, obj):
        self.tpe = tpe
        self.obj = obj

class ObjectTracker:
    TRACKERS = []
    def __init__(self, func):
        self.func = func
        self.objs: List[HeapObject] = []

    def add_object(self, tpe, obj):
        self.objs.append(HeapObject(tpe, obj))

    def free(self, scope_for_free, builder: ir.IRBuilder, exception: ir.Ret):
        for obj in self.objs:
            if obj.obj == exception.return_value: continue
            builder.call(scope_for_free[obj.tpe + "__free__"], [obj.obj])

    @classmethod
    def create_tracker(cls, func):
        t = ObjectTracker(func)
        cls.TRACKERS.append(t)
        return t

    @classmethod
    def get_tracker(cls, func) -> "ObjectTracker":
        return [tracker for tracker in cls.TRACKERS if tracker.func == func][0]