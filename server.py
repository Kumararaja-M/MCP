from mcp.server.fastmcp import FastMCP
import time

mcp = FastMCP(host="0.0.0.0", port=8033)


@mcp.tool()
def add(a:int, b:int) ->int:
    """Add two numbers"""
    return a+b


@mcp.tool()
def multiply(a:int, b:int) ->int:
    """Multiply two numbers"""
    return a*b


@mcp.tool()
def add_then_multiply(a:int, b:int, c:int) ->int:
    """
    Add a and b, then multiply the sum by c.
    Example: (a + b) * c
    """
    sum_result = add(a,b)

    return multiply(sum_result, c)



if __name__ == "__main__":
    mcp.run(transport="streamable-http")
