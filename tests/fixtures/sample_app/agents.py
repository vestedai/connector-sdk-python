from vested_connect import Instruction, agent


@agent(
    key="sample.insights",
    name="Sample Insights",
    model="openai:gpt-4o",
    instructions=[Instruction(type="system", position=0, body="sample")],
)
class Insights:
    pass
