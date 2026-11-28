"""Drive an installed brickscape-mcp over MCP and exercise every tool, prompt and resource.

    python tools/smoke_client.py /path/to/brickscape-mcp [--no-render]
Exit code 0 only if every check passes. Uses the current HOME / environment.
"""
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TINY = {"name": "smoke tiny", "board": {"width": 16, "depth": 16}, "seed": 3, "ops": [
    {"op": "block", "area": {"rect": [2, 2, 6, 6]}, "height": 3},
    {"op": "tree", "kind": "oak", "size": "small", "at": [11, 11]}]}
results = []


def ok(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)


async def main(server, render):
    p = StdioServerParameters(command=server, args=[], env=dict(os.environ))
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            ok("initialize + instructions", init.instructions and "BrickScape" in init.instructions)
            listed = (await s.list_tools()).tools
            tools = {t.name for t in listed}
            ok("11 tools listed", len(tools) == 11, ", ".join(sorted(tools)))
            refs = [t.name for t in listed if "$ref" in json.dumps(t.input_schema)]
            ok("no $ref in tool input schemas (form-based inspectors can't resolve them)", not refs, ", ".join(refs))
            ok("3 prompts listed", len((await s.list_prompts()).prompts) == 3)
            ok("3 resources + 1 template", len((await s.list_resources()).resources) == 3
               and len((await s.list_resource_templates()).resource_templates) == 1)

            async def call(name, args, expect):
                res = await s.call_tool(name, args)
                txt = res.content[0].text if res.content and hasattr(res.content[0], "text") else ""
                good = not res.is_error and (expect(res) if callable(expect) else expect in txt)
                ok(f"tool {name}", good, (txt.splitlines() or ["(image)"])[0][:90])
                return txt

            await call("guide", {}, "BrickScape guide")
            await call("search_parts", {"query": "plant leaves", "limit": 3}, "2417")
            await call("part_info", {"part": "3001"}, "Brick  2 x  4")
            plan = json.loads((await s.read_resource("brickscape://examples/garden-20")).contents[0].text)
            ok("resource example plan", plan.get("ops"))
            ok("resource plan schema", "Hill" in (await s.read_resource("brickscape://schema/plan")).contents[0].text)
            await call("build", {"plan": json.dumps(plan)}, "VALID")
            await call("build", {"plan": json.dumps(TINY)}, "VALID")
            out = os.path.join(os.environ.get("BRICKSCAPE_OUT", "brickscape-out"), "smoke-tiny", "model.ldr")
            await call("check", {"path": out}, "VALID")
            await call("parts_list", {"name": "smoke tiny"}, "parts in")
            await call("export", {"name": "smoke tiny"}, ".io")
            bad = await s.call_tool("build", {"plan": json.dumps({"ops": [{"op": "tree", "at": [1, 1], "size": "huge"}]})})
            ok("bad plan rejected with field name", bad.is_error and "size" in bad.content[0].text)
            pr = await s.get_prompt("design_scene", {"description": "a pond"})
            ok("prompt design_scene", "pond" in pr.messages[0].content.text)
            pr = await s.get_prompt("design_scene", {"description": "a pond", "width": "", "depth": "20", "source": ""})
            ok("prompt with empty form boxes", "32 x 20" in pr.messages[0].content.text)
            for name, args in (("recreate_photo", {"photo_path": "ref.png", "width": ""}), ("check_model", {"path": "m.ldr", "source": ""})):
                ok(f"prompt {name}", (await s.get_prompt(name, args)).messages)
            if render:
                await call("render", {"name": "smoke tiny", "resolution": 240},
                           lambda res: res.content and res.content[0].type == "image")
                await call("instructions", {"name": "smoke tiny", "parts_per_step": 12}, "instructions.pdf")
    failed = [n for n, g in results if not g]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1], "--no-render" not in sys.argv)))
