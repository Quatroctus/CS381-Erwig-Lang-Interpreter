import typing
from command import execute_program
from parse import parse_input
from runtime import RuntimeStack, CallTypeEnum


def get_limited_input(prompt: str, valid: typing.Collection[str], convert: typing.Callable):
    """
    Obtain string input validate it and convert it.
    @param prompt: The prompt to display to the user.
    @param valid: A collection of strings which are valid inputs.
    @param convert: A function which converts the string value into
                    it's actual return value.
    @returns The converted input as determined by the convert function.
    """
    ins = input(prompt).upper()
    while ins not in valid:
        ins = input(prompt).upper()
    return convert(ins)


def read_input():
    """
    Obtain the typing, function calltype, and Erwig syntax code until q or quit is entered.
    @returns A tuple of the typing, calltype, and code as a list of lines.
    """
    typing: CallTypeEnum = get_limited_input("Call Type: ", ["CBV", "CBR", "CBVR", "CBNEED", "CBNAME"], lambda x: CallTypeEnum[x])
    calltype: bool = get_limited_input("Typing: ", ["S", "STATIC", "D", "DYNAMIC"], lambda x: x == "S" or x == "STATIC")
    user_input: str = input()
    raw_input: str = ""
    while user_input != "q" and user_input != "quit":
        raw_input += user_input
        user_input = input()
    lines: typing.List[str] = list(filter(None, map(str.strip, raw_input.replace(";", "\n").replace("{", "{\n").replace("}", "\n}\n").splitlines())))
    return typing, calltype, lines


def main():
    type, calltype, input = read_input()
    commands, lines = parse_input(input, type, calltype)
    stack: RuntimeStack = RuntimeStack(typing, calltype)
    execute_program(stack, calltype, commands, lines)


if __name__ == "__main__":
    main()
