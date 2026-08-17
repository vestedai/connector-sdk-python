def test_proto_imports() -> None:
    from vested_connect.proto import connector_hub_pb2
    assert hasattr(connector_hub_pb2, "ConnectorMsg")
    assert hasattr(connector_hub_pb2, "HubMsg")


def test_sdk_version() -> None:
    import vested_connect
    assert vested_connect.__version__ == "0.6.0"
