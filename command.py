import re
import enum
import typing
from runtime import RuntimeStack, ActivatationRecord, CallTypeEnum, Function


class CommandTypeEnum(enum.Enum):
    """Enum for Command types."""
    DECLARE_VAR = 0
    DECLARE_FUNC = 1
    ASSIGN_VAR = 2
    FUNC_CALL = 3
    RETURN = 4
    VALUE_RESULT = 5
    STORE_FUNC_RET = 6
    CLEAR_FUNC_RET = 7
    SCOPE_NEW = 8
    SCOPE_DEL = 9
    CONDITIONAL = 10

    def __str__(self) -> str:
        """Remove the CommandTypeEnum from string representation."""
        return super.__str__(self)[15:]


def translate_vars(expr: str):
    """
    Translate all variable names into Python code for 'eval' call.
    @param expr: The expression to translate.
    @returns The translated expression.
    """
    elems = list(filter(None, re.split("(\".+\")|(\()|(\))|(\s?\+\s?)|(\s?-\s?)|(\s?\*\s?)|(\s?/\s?)", expr)))
    expr_list = []
    for elem in elems:
        if elem.strip() in ["+", "-", "*", "/", "(", ")"] or elem.isnumeric():
            expr_list.append(elem)
        elif elem[0] == "\"":
            expr_list.append(f'stack.func_ret({elem})')
        else:
            expr_list.append(f"stack.get_value('{elem}')")
    return "".join(expr_list)


def new_scope(stack: RuntimeStack, calltype: CallTypeEnum):
    """
    Create a new scope and push it onto the RuntimeStack.
    @param stack: The RuntimeStack.
    @param calltype: The program's function calltype.
    """
    stack.push_record(ActivatationRecord(calltype))


def del_scope(stack: RuntimeStack, func: bool):
    """
    Delete a scope from the RuntimeStack.
    @param stack: The RuntimeStack.
    @param func: Is this a function ActivationRecord.
    @returns None.
    """
    if func:
        stack.pop_func()
    stack.pop_record()


def declare_variable(stack: RuntimeStack, name: str):
    """
    Execute a variable declaration.
    @param stack: The RuntimeStack.
    @param name: The variable name to declare.
    @returns None.
    """
    stack.declare_value(name)


def assign_variable(stack: RuntimeStack, name: str, value: str):
    """
    Execute a variable assignment.
    @param stack: The RuntimeStack.
    @param name: The variable name to assign to.
    @param value: The expression value to assign.
    @returns None.
    """
    expr = translate_vars(value)
    stack.set_value(name, str(eval(expr)))


def function_return(stack: RuntimeStack, value: str):
    """
    Execute the function return statement.
    @param stack: The RuntimeStack.
    @param value: The expression value to return.
    @returns None.
    """
    expr = translate_vars(value)
    stack.set_ret(eval(expr))


def value_result(stack: RuntimeStack, name: str, args: typing.List[str]):
    """
    Execute the value results step(copy parameter names over to argument names).
    @param stack: The Runtime Stack.
    @param name: The name of the function.
    @param args: The argument list which was passed to the called function.
    @returns None.
    """
    func: Function = stack.get_value(name)
    rindex = stack.pop_func()
    func_record = stack.records.pop()
    for i in range(len(func.params)):
        param = func.params[i]
        arg: str = args[i]
        if not arg.isnumeric():
            stack.set_value(arg, func_record.get_value(param))
    stack.records.append(func_record)
    stack.push_func(rindex, func.name)


def declare_function(stack: RuntimeStack, name: str, commands: list, params: typing.List[str]):
    """
    Push a function declaration onto the stack.
    @param stack: The RuntimeStack.
    @param name: The function's name.
    @param commands: The command data associated with the function.
    @param params: The parameter names associated with the function.
    @returns None.
    """
    stack.declare_value(name)
    stack.set_value(name, Function(name, commands, params, len(stack.records)-1))


def apply_func_params(stack: RuntimeStack, record: ActivatationRecord, params: list, arguments: list, calltype: CallTypeEnum):
    """
    Based on the calltype place function call arguments into the ActivationRecord.
    @param stack: The RuntimeStack, only here for the eval call.
    @param record: The functions ActivationRecord.
    @param params: The parameter names for the function.
    @param arguments: The args the function is being called with.
    @param calltype: The function calltype.
    @returns None.
    """
    for i in range(len(params)):
        if calltype == CallTypeEnum.CBNAME or calltype == CallTypeEnum.CBNEED or calltype == CallTypeEnum.CBR:
            record.record[params[i]] = translate_vars(arguments[i])
        else:
            record.record[params[i]] = eval(translate_vars(arguments[i]))


def call_function(stack: RuntimeStack, fname: str, args: list, calltype: CallTypeEnum):
    """
    Execute a function call.
    @param stack: The RuntimeStack.
    @param fname: The name of the function to execute.
    @param args: The arguments to call the function with.
    @param calltype: The function calltype.
    @returns None.
    """
    func: Function = stack.get_value(fname)
    rfunc = ActivatationRecord(calltype)
    apply_func_params(stack, rfunc, func.params, args, calltype)
    stack.push_record(rfunc)
    stack.push_func(func.rindex, fname)
    fcommands, line_data = func.commands
    execute_program(stack, calltype, fcommands, line_data)


def conditional(stack: RuntimeStack, left: str, cond: str, right: str, ifcommands: list, ecommands: tuple, calltype: CallTypeEnum):
    """
    Execute a conditional block.
    @param stack: The RuntimeStack.
    @param left: The left side of the conditional expression.
    @param cond: The conditional to compare the left and right expressions.
    @param right: The right side of the conditional expression.
    @param ifcommands: The commands to execute if the conditional expression is true.
    @param ecommands: The commands to execute if the conditional expression is false.
    @param calltype: The function calltype.
    @returns None.
    """
    cond_lookup = {
        "=": "==", "==": "==",
        "\\=": "!=", "/=": "!=", "!=": "!=",
        ">": ">", "<": "<",
        "=<": "<=", "<=": "<=",
        ">=": ">=", "=>": ">="
    }

    cond_expr = translate_vars(left) + cond_lookup[cond] + translate_vars(right)
    boolean = eval(cond_expr)
    if boolean:
        stack.push_record(ActivatationRecord(calltype))
        ifcommands, line_data = ifcommands
        execute_program(stack, calltype, ifcommands, line_data)
    else:
        stack.push_record(ActivatationRecord(calltype))
        ecommands, line_data = ecommands
        execute_program(stack, calltype, ecommands, line_data)


class Command:

    def __init__(self, type: CommandTypeEnum, data: tuple):
        self.type = type
        self.data = data

    def apply(self, stack: RuntimeStack, calltype: CallTypeEnum):
        """
        Execute this command on the RuntimeStack with the specified calltype.
        @param self: This command.
        @param stack: The RuntimeStack.
        @param calltype: The function calltype.
        @returns None.
        """
        if self.type == CommandTypeEnum.SCOPE_NEW:
            new_scope(stack, calltype)
        elif self.type == CommandTypeEnum.SCOPE_DEL:
            del_scope(stack, self.data["func"])
        elif self.type == CommandTypeEnum.DECLARE_VAR:
            declare_variable(stack, self.data["name"])
        elif self.type == CommandTypeEnum.ASSIGN_VAR:
            assign_variable(stack, self.data["name"], self.data["value"])
        elif self.type == CommandTypeEnum.FUNC_CALL:
            call_function(stack, self.data["name"], self.data["params"], calltype)
        elif self.type == CommandTypeEnum.STORE_FUNC_RET:
            stack.store_func_returns(self.data["uuid"])
        elif self.type == CommandTypeEnum.RETURN:
            function_return(stack, self.data["value"])
        elif self.type == CommandTypeEnum.VALUE_RESULT and calltype == CallTypeEnum.CBVR:
            value_result(stack, self.data["name"], self.data["params"])
        elif self.type == CommandTypeEnum.DECLARE_FUNC:
            declare_function(stack, self.data["name"], self.data["commands"], self.data["params"])
        elif self.type == CommandTypeEnum.CONDITIONAL:
            conditional(stack, self.data["left"], self.data["cond"], self.data["right"], self.data["if"], self.data["else"], calltype)

    def __str__(self):
        if self.type == CommandTypeEnum.DECLARE_FUNC:
            s = f"{str(self.type)}: {self.data['name']}\n"
            s += "".join([f"   {str(c)}\n" for c in self.data["commands"]])
            return s
        elif self.type == CommandTypeEnum.CONDITIONAL:
            s = f"{str(self.type)}:\nif {self.data['left']} {self.data['cond']} {self.data['right']}\n"
            s += "".join([f"    {str(c)}\n" for c in self.data["if"]])
            s += "else\n"
            s += "".join([f"    {str(c)}\n" for c in self.data["else"]])
            return s
        else:
            return f"{str(self.type)}: {self.data}"


def execute_program(stack: RuntimeStack, calltype: CallTypeEnum, commands: typing.List[Command], line_data: typing.List[typing.Tuple[int, int, int]], ):
    """
    Execute the list of commands on the stack and display the stack.
    @param stack: The RuntimeStack to perform execution on.
    @param calltype: This programs function call type.
    @param commands: The list of commands to execute.
    @param line_data: Determines when we should print a RuntimeStack.
    @returns None
    """
    i: int = 0
    for cline, ccount, lineno in line_data:
        for _ in range(ccount):
            c = commands[i]
            if c.type == CommandTypeEnum.FUNC_CALL:
                print('    ' * len(stack.func_stack), f"Before {c.data['name']} -> {str(stack)} #{lineno+1}")
            elif c.type == CommandTypeEnum.CONDITIONAL:
                print('    ' * len(stack.func_stack), f"Before if {c.data['left']} {c.data['cond']} {c.data['right']} {str(stack)} #{lineno+1}")
            c.apply(stack, calltype)
            if cline == i and not c.type == CommandTypeEnum.CONDITIONAL:
                print('    ' * len(stack.func_stack), str(stack) + f" After #{lineno + 1}")
            i += 1
