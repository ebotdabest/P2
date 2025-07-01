class NoTypeError(Exception):
    def __init__(self, var):
        self.var = var

    def __repr__(self):
        return f"{self.var} was not given a type! Please type hint one!"

    def __str__(self):
        return self.__repr__()

class SymbolNotFound(Exception):
    def __init__(self, var):
        self.var = var

    def __repr__(self):
        return f"{self.var} was trying to be modified but was not found!"

    def __str__(self):
        return self.__repr__()