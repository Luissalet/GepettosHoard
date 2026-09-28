"""One real MCP stdio call; JSON arguments come from a file, never shell interpolation."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call(data_dir, tool, arguments):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.external_mcp", "--data-dir", str(Path(data_dir).resolve())],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            if tool == "list":
                return (await session.list_tools()).model_dump(mode="json")
            return (await session.call_tool(tool, arguments)).model_dump(mode="json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("tool")
    parser.add_argument("--arguments", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.arguments.read_text("utf-8-sig")) if args.arguments else {}
    result = asyncio.run(call(args.data_dir, args.tool, payload))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open("x", encoding="utf-8") as output:
            output.write(text)
    else:
        print(text)
    if result.get("isError"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
