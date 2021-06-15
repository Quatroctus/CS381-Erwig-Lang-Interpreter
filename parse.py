import re
import typing
from uuid import uuid4
from runtime import CallTypeEnum
from command import Command, CommandTypeEnum


# Useful regular expressions.
name = "[A-Za-z0-9_]"
r_expr = "[A=Za-z0-9_ \t\(\)\+\-\*/]"
r_params = f"(?:(?:{name}+\s+{name}+(?:\s*,\s*{name}+\s+{name}+)+)|(?:{name}+\s+{name}+))?"
r_args = f"({r_expr}+(\s*,\s*{r_expr}+)+)|({r_expr}+)?"
r_cond = "(?:(?:=)|(?:>)|(?:<)|(?:>=)|(?:<=)|(?:!=))"


def collect_func_calls(value: str) -> typing.Tuple[str, typing.List[typing.Tuple[str, str, int, int]]]:
    """
    Generate function call data for each function call within the value expression.
    @param value: The value expression to collect function calls for.
    @returns A tuple of the modified value expression and the function call data.
    """
    func_calls = []
    i = 0
    while i < len(value):
        # Does the string starting at i match a funcation call.
        if match := re.match(f"{name}+\s*\(", value[i:]):

            # Extract the entire string for this function call by counting parenthesis.
            parens = 1
            j = i + len(match.group(0))
            while parens > 0:
                if value[j] == "(":
                    parens += 1
                elif value[j] == ")":
                    parens -= 1
                j += 1

            # Assign a uuid for the result of this function call.
            uuid = uuid4()
            func_calls.append((value[i:j], str(uuid), i, j))
            i += len(match.group(0)) - 1
        i += 1
    # Sort the function calls by smallest ending position(call order).
    func_calls.sort(key=lambda call: call[3])

    # Does index overlap with any other function call.
    overlap = lambda index: any([index < m and index > l for _, _, l, m in func_calls])

    # Obtain the function call overlaps for n and m.
    get_overlaps = lambda n, m: list(filter(None, [call if call[3] < m and call[3] > n else None for call in func_calls]))

    for i in range(len(func_calls)):
        scall, uuid, n, m = func_calls[i]
        if not overlap(m):
            # Replace the first occurance of scall in the passed value expression with it's uuid with surrounding quotes.
            value = value.replace(scall, f'"{uuid}"', 1)
            overlaps = get_overlaps(n, m)
            # For all function calls that overlap with this function,
            # replace the function call with it's uuid with surrounding quotes in the scall string.
            for ocall, ouuid, _, _ in overlaps:
                scall = scall.replace(ocall, f'"{ouuid}"', 1)
            func_calls[i] = (scall, uuid, n, m)
    return value, func_calls


def gen_func_call_commands(func_calls: typing.List[typing.Tuple[str, str, int, int]]) -> typing.List[Command]:
    """
    Convert function call data into a list of command data.
    @param func_calls: The list of function call data.
    @returns A list of Commands that represent these function calls.
    """
    commands = []
    for scall, uuid, _, _ in func_calls:
        fname = re.split("\s*\(", scall)[0]

        # Args are comma separated values, but we need to remove the two surrounding parenthesis.
        args = re.split("\s*,\s*", scall)
        args[0] = "(".join(args[0].split("(")[1:])
        args[-1] = args[-1][:-1]

        commands.append(Command(CommandTypeEnum.FUNC_CALL, {"name": fname, "params": args}))
        commands.append(Command(CommandTypeEnum.STORE_FUNC_RET, {"uuid": uuid}))
        commands.append(Command(CommandTypeEnum.VALUE_RESULT, {"name": fname, "params": args}))
        commands.append(Command(CommandTypeEnum.SCOPE_DEL, {"func": True}))
    return commands


def obtain_scoped_lines(i: int, input: typing.List[str]) -> typing.List[str]:
    """
    Obtain all of the lines within a scoped body.
    @param i: The current index into input.
    @param input: The line input.
    @returns A tuple of the ending index and the lines which exist within the scoped body.
    """
    lines = []
    scope_count = 1
    while scope_count > 0:
        i += 1
        l = input[i]
        if l.endswith("{"):
            scope_count += 1
        elif l.endswith("}"):
            scope_count -= 1
        lines.append(l)
    return i, lines


def parse_input(input: typing.List[str], type: bool, calltype: CallTypeEnum, lineno: int = 0) -> typing.Tuple[typing.List[Command], typing.List[typing.Tuple[int, int, int]]]:
    """
    Perform lexical analysis on the input of lines.
    @param input: The lines of code to parse.
    @param type: The typing of the language(static or dynamic).
    @param calltype: The function calltype.
    @returns A tuple containing the list of commands and the line data for the commands.
    """
    clines: typing.List[int] = []
    commands: typing.List[Command] = []
    i = 0
    while i < len(input):
        j = i
        ccount = len(commands)
        line = input[i]
        if line == "{":                                                            # Scope new.
            commands.append(Command(CommandTypeEnum.SCOPE_NEW, {}))
        elif line == "}":                                                          # Scope delete.
            commands.append(Command(CommandTypeEnum.SCOPE_DEL, {"func": False}))
        elif match := re.match(f"{name}+\s+{name}+\({r_params}\)\s*{'{'}", line): # Declare a function.
            smatch = match.group(0)
            fname = re.split("\s+", re.match(f"{name}+\s+{name}+", smatch).group(0))[1]
            # Split the parameter section on commas and remove the type by spliting on whitespace and taking the second value.
            fparams = list(map(lambda x: re.split("\s+", x)[1], re.split("\s*,\s*", re.findall(f"\({r_params}\)", smatch)[0][1:-1])))
            # Obtain the function body and update the index(i) into input appropriately.
            i, func_lines = obtain_scoped_lines(i, input)
            # Remove the scope delete line from the function body.
            func_lines.pop()
            # Parse the function input.
            fcommand_data = parse_input(func_lines, type, calltype, lineno + j + 1)
            commands.append(Command(CommandTypeEnum.DECLARE_FUNC, {"name": fname, "commands": fcommand_data, "params": fparams}))
        elif match := re.match(f"return\s+{r_expr}+", line):                       # Return an expression.
            smatch = match.group(0)
            # Grab the return value expression using regex.
            value = list(filter(None, re.split("return\s+", smatch)))[0]
            # Obtain the function calls within the expression and the updated expression.
            value, func_calls = collect_func_calls(value)

            # Extend the command list with the function call commands.
            commands.extend(gen_func_call_commands(func_calls))
            commands.append(Command(CommandTypeEnum.RETURN, {"value": value}))
        elif match := re.match(f"if\s+{r_expr}+\s*{r_cond}\s*{r_expr}+\s*{'{'}", line):
            smatch = match.group(0)
            # Remove the if and any spaces proceeding it.
            submatch = smatch[len(re.match("if\s+", smatch).group(0)):-1]
            # Split the conditional expression on the conditional operator to obtain the left and right expressions.
            left, right = map(str.strip, re.split(f"\s*{r_cond}\s*", submatch))
            # Obtain the condition operator.
            condition = re.findall(f"{r_cond}", submatch)[0]

            # Get the if statement body.
            i, if_lines = obtain_scoped_lines(i, input)

            # If there is an else statement obtain the else statement body.
            else_lines = []
            if input[i+1].startswith("else"):
                i, else_lines = obtain_scoped_lines(i+1, input)

            # Parse the if and else statement body into lists of commands.
            if_command_data = parse_input(if_lines, type, calltype, lineno + j + 1)
            else_command_data = parse_input(else_lines, type, calltype, lineno + j + len(if_lines) + 2)
            commands.append(Command(CommandTypeEnum.CONDITIONAL, {"left": left, "cond": condition, "right": right, "if": if_command_data, "else": else_command_data}))
        elif match := re.match(f"{name}+\s+{name}+\s*:?=\s*{r_expr}+", line):      # Declare and assign a variable.
            smatch = match.group(0)
            # Separate the type and variable name then the variable name from the type.
            vname = re.split("\s+", re.match(f"{name}+\s+{name}+", smatch).group(0))[1]
            # Separate the left hand and right hand assignment expression and the value is the right.
            value = re.split("\s*:?=\s*", smatch)[1]
            # Obtain the function calls in the expression and update the expression appropriately.
            value, func_calls = collect_func_calls(value)

            # Extend the command list with the function call commands.
            commands.extend(gen_func_call_commands(func_calls))
            commands.append(Command(CommandTypeEnum.DECLARE_VAR, {"name": vname}))
            commands.append(Command(CommandTypeEnum.ASSIGN_VAR, {"name": vname, "value": value}))
        elif match := re.match(f"{name}+\s+{name}+", line):                        # Declare a variable.
            smatch = match.group(0)
            # Separate the type and variable name from eachother.
            vname = re.split("\s+", re.match(f"{name}+\s+{name}+", smatch).group(0))[1]
            commands.append(Command(CommandTypeEnum.DECLARE_VAR, {"name": vname}))
        elif match := re.match(f"{name}+\s*:?=\s*{r_expr}+", line):                # Assign variable.
            smatch = match.group(0)
            # Separate the variable name and the expression value from each other.
            vname, value = re.split("\s*:?=\s*", smatch)
            # Obtain the function calls in the expression and update the expression appropriately.
            value, func_calls = collect_func_calls(value)

            # Extend the command list with the function call commands.
            commands.extend(gen_func_call_commands(func_calls))
            commands.append(Command(CommandTypeEnum.ASSIGN_VAR, {"name": vname, "value": value}))
        # Populate the line data with this lines ending command index, number of commands, and line number.
        clines.append((len(commands)-1, len(commands) - ccount, lineno + j))
        i += 1
    return commands, clines
