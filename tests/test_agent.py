from vested_connect import Instruction, agent


def test_agent_decorator_stamps_declaration() -> None:
    @agent(
        key="acme.insights",
        name="Insights",
        model="openai:gpt-4o",
        instructions=[Instruction(type="system", position=0, body="hello")],
    )
    class Insights:
        pass

    decl = Insights.__vested_agent__  # type: ignore[attr-defined]
    assert decl.key == "acme.insights"
    assert decl.model == "openai:gpt-4o"
    assert decl.name == "Insights"
    assert len(decl.instructions) == 1
    assert decl.instructions[0].body == "hello"


def test_agent_with_no_instructions_defaults_to_empty_list() -> None:
    @agent(key="x.y", name="X", model="openai:gpt-4o")
    class X:
        pass
    assert X.__vested_agent__.instructions == []  # type: ignore[attr-defined]


def test_agent_with_model_config() -> None:
    @agent(
        key="x.y",
        name="X",
        model="openai:gpt-4o",
        model_config={"temperature": 0.7, "max_steps": 10},
    )
    class X:
        pass
    assert X.__vested_agent__.model_config == {"temperature": 0.7, "max_steps": 10}  # type: ignore[attr-defined]
