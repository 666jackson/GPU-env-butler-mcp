import asyncio, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    p = StdioServerParameters(command=sys.executable, args=["server.py"])
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            print("tools:", [t.name for t in tools])
            print("prompts:", [x.name for x in (await s.list_prompts()).prompts])
            for t in tools:
                res = await s.call_tool(t.name, {})
                print(f"--- {t.name}: {res.content[0].text}")
asyncio.run(main())
