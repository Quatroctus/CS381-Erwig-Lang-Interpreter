import enum
import typing
from dataclasses import dataclass

class CallTypeEnum(enum.Enum):
    """Enum for function calltypes."""
    CBV = 0
    CBR = 1
    CBVR = 2
    CBNEED = 3
    CBNAME = 4


@dataclass
class Function:
    """Represents a function declaration in the program."""

    def __init__(self, name: str, commands: list, params: list, rindex: int):
        self.name = name
        self.params = params
        self.commands = commands
        self.rindex = rindex


class ActivatationRecord:
    """
    Represents a single ActivationRecord otherwise known as a scope.
    @data record: The variable and function entries.
    @data calltype: The function calltype of the program.
    """

    def __init__(self, calltype: CallTypeEnum) -> None:
        self.record: dict = {}
        self.calltype = calltype

    def get_value(self, stack, name: str, fname: str = None):
        """
        Obtain a variable value from this ActivationRecord with name.
        @param stack: The RuntimeStack, only here for the eval call.
        @param name: The variable name to obtain the value of.
        @param fname: The currently executing function name, used when static typing should be applied.
        @returns If the variable exists the value associated, otherwise None.
        """
        def obtain():
            """Obtain a value from the record."""
            val = self.record[name]
            if isinstance(val, str):
                val = eval(val)
            if self.calltype == CallTypeEnum.CBNEED and val != self.record[name]:
                self.record[name] = val
            return val
        if fname:
            # Iterate over the kets until the function is found assign return if name is found first.
            # This preserves the declaration order in statically typed execution.
            for k,e in self.record.items():
                if k == fname:
                    return None
                if k == name:
                    return obtain()
            return None
        if name in self.record.keys():
            return obtain()
        return None

    def set_value(self, stack, name: str, value, fname: str = None) -> bool:
        """
        Assign a value to this ActivationRecord to the name.
        @param stack: The RuntimeStack, only here for the eval call.
        @param name: The variable name to assign to.
        @param value: The value to assign.
        @param fname: The function name, used when static typing should be applied.
        @returns Whether that variable was assigned in this ActivationRecord.
        """
        # Define a function to reduce code duplication.
        def assign(): self.record[name] = eval(value) if isinstance(value, str) else value
        if fname:
            # Iterate over the keys until the function is found assign if name is found first.
            # This preserves declaration order in statically typed execution.
            for k in self.record.keys():
                if k == fname:
                    return False
                if k == name:
                    assign()
                    return True
        elif name in self.record.keys():
            assign()
            return True
        return False

    def __str__(self) -> str:
        return f"<{', '.join([str(k) + ': ' + ('?' if e == None else '{}' if isinstance(e, Function) else str(e)) for k, e in reversed(self.record.items())])}>"


class RuntimeStack:
    """
    Represent a programs RuntimeStack.
    @data records: The list of ActivationRecords.
    @data typing: Static or Dynamic typing.
    @data calltype: The programs function calltype.
    @data ret: The last function return value.
    @data func_stack: The function call stack.
    @data func_returns: The function call return value storage.
    """

    def __init__(self, type: bool, calltype: CallTypeEnum) -> None:
        self.records: typing.List[ActivatationRecord] = []
        self.typing = type
        self.calltype = calltype
        self.ret = None
        self.func_stack = []
        self.func_returns = {}

    def store_func_returns(self, uuid: str):
        """
        Store a function return value mapped to the uuid.
        @param uuid: The uuid to map the current return value to.
        @returns None.
        """
        self.func_returns[uuid] = self.ret
        self.ret = None

    def func_ret(self, uuid: str):
        """
        Obtain the function call return value from the function return storage.
        @param uuid: The uuid of the function call return to obtain.
        @returns The value the function call with the uuid obtained from storage.
        """
        return self.func_returns[uuid]

    def push_record(self, record: ActivatationRecord):
        """
        Push an ActivationRecord onto the RuntimeStack.
        @param record: The ActivationRecord to push onto the stack.
        """
        self.records.append(record)

    def pop_record(self):
        """
        Pop an ActivationRecord off of the RuntimeStack.
        @returns None.
        """
        self.records.pop()

    def push_func(self, rindex:int , fname: str):
        """
        Push function call data onto the stack.
        @param rindex: The function declaration index.
        @param fname: The function's name.
        @returns None.
        """
        self.func_stack.append((rindex, len(self.records)-1, fname))

    def pop_func(self) -> typing.Tuple[int, int, str]:
        """
        Pop the last function call storage from the stack.
        @returns The function call data that was popped off of the stack.
        """
        return self.func_stack.pop()

    def in_func(self) -> bool:
        """
        Are we currently executing from inside a function.
        @returns If we are executing from inside a funciton.
        """
        return self.func_stack

    def set_ret(self, value):
        """
        Assign the function return storage to the value.
        @param value: The value to set the function return to.
        @returns None.
        """
        self.ret = value

    def get_ret(self):
        """Obtain the last value returned from a function."""
        return self.ret

    def get_value(self, name: str):
        """
        Retrieve a value from the RuntimeStack with name.
        @param name: The name of the variable to retrieve.
        @returns The value stored under the variable name.
        """
        if self.in_func() and not self.typing: # If we are executing a function and we are statically typed.
            rindex, sindex, fname = self.func_stack[-1]
            # First check the scopes from inside the function call.
            for i in range(len(self.records)-1, sindex-1, -1):
                value = self.records[i].get_value(self, name)
                if value != None:
                    return value
            # Second check the scopes from declaration scope.
            for i in range(rindex, -1, -1):
                value = self.records[i].get_value(self, name, fname)
                if value != None:
                    return value
        else:
            # Check the scopes from new to old otherwise.
            for i in range(len(self.records)-1, -1, -1):
                value = self.records[i].get_value(self, name)
                if value != None:
                    return value
        return None


    def set_value(self, name: str, value) -> bool:
        """
        Assign a value in the RuntimeStack with name to value.
        @param name: The name of the variable.
        @param value: The expression value.
        @return If the value was able to be assigned.
        """
        if self.in_func() and not self.typing: # If we are executing a function and we are statically typed.
            rindex, sindex, fname = self.func_stack[-1]
            # First check the scopes from inside the function call.
            for i in range(len(self.records)-1, sindex-1, -1):
                if self.records[i].set_value(self, name, eval(value)):
                    return True
            # Second check the function scopes from declaration scope.
            for i in range(rindex, -1, -1):
                if self.records[i].set_value(self, name, eval(value), fname):
                    return True
        else:
            # Check scopes from new to old otherwise.
            for i in range(len(self.records)-1, -1, -1):
                if self.records[i].set_value(self, name, value):
                    return True
        return False

    def declare_value(self, name: str):
        """
        Store an uninitialized value in the current record.
        @param name: The new variable name.
        @returns None.
        """
        self.records[-1].record[name] = None

    def __str__(self) -> str:
        return (f"Ret: {self.ret}" if self.in_func() and self.ret else "") + f"[{', '.join([str(r) for r in reversed(self.records)])}]"
