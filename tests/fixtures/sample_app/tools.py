from vested_connect import BaseModel, Field, ToolHandler, tool


@tool("sample.insights.echo", description="Sample echo.")
class Echo(ToolHandler):
    class Args(BaseModel):
        text: str = Field(description="Text to echo.")

    class Result(BaseModel):
        echoed: str

    async def handle(self, args, ctx):  # type: ignore[no-untyped-def]
        return Echo.Result(echoed=args.text)
