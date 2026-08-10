import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResultKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESULT_KIND_SINGLE: _ClassVar[ResultKind]
    RESULT_KIND_ROWSET: _ClassVar[ResultKind]
RESULT_KIND_SINGLE: ResultKind
RESULT_KIND_ROWSET: ResultKind

class ConnectorMsg(_message.Message):
    __slots__ = ("hello", "register", "tool_call_response", "heartbeat", "credential_op_response")
    HELLO_FIELD_NUMBER: _ClassVar[int]
    REGISTER_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALL_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    CREDENTIAL_OP_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    hello: Hello
    register: Register
    tool_call_response: ToolCallResponse
    heartbeat: Heartbeat
    credential_op_response: CredentialOpResponse
    def __init__(self, hello: _Optional[_Union[Hello, _Mapping]] = ..., register: _Optional[_Union[Register, _Mapping]] = ..., tool_call_response: _Optional[_Union[ToolCallResponse, _Mapping]] = ..., heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., credential_op_response: _Optional[_Union[CredentialOpResponse, _Mapping]] = ...) -> None: ...

class Hello(_message.Message):
    __slots__ = ("sdk_language", "sdk_version", "worker_id")
    SDK_LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    SDK_VERSION_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    sdk_language: str
    sdk_version: str
    worker_id: str
    def __init__(self, sdk_language: _Optional[str] = ..., sdk_version: _Optional[str] = ..., worker_id: _Optional[str] = ...) -> None: ...

class Register(_message.Message):
    __slots__ = ("baseline_fingerprint", "agents", "credential_schema")
    BASELINE_FINGERPRINT_FIELD_NUMBER: _ClassVar[int]
    AGENTS_FIELD_NUMBER: _ClassVar[int]
    CREDENTIAL_SCHEMA_FIELD_NUMBER: _ClassVar[int]
    baseline_fingerprint: str
    agents: _containers.RepeatedCompositeFieldContainer[AgentDecl]
    credential_schema: CredentialSchemaDecl
    def __init__(self, baseline_fingerprint: _Optional[str] = ..., agents: _Optional[_Iterable[_Union[AgentDecl, _Mapping]]] = ..., credential_schema: _Optional[_Union[CredentialSchemaDecl, _Mapping]] = ...) -> None: ...

class CredentialSchemaDecl(_message.Message):
    __slots__ = ("kind", "title", "help_text", "fields")
    KIND_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    HELP_TEXT_FIELD_NUMBER: _ClassVar[int]
    FIELDS_FIELD_NUMBER: _ClassVar[int]
    kind: str
    title: str
    help_text: str
    fields: _containers.RepeatedCompositeFieldContainer[CredentialFieldDecl]
    def __init__(self, kind: _Optional[str] = ..., title: _Optional[str] = ..., help_text: _Optional[str] = ..., fields: _Optional[_Iterable[_Union[CredentialFieldDecl, _Mapping]]] = ...) -> None: ...

class CredentialFieldDecl(_message.Message):
    __slots__ = ("key", "label", "type", "required", "placeholder", "options")
    KEY_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_FIELD_NUMBER: _ClassVar[int]
    PLACEHOLDER_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    key: str
    label: str
    type: str
    required: bool
    placeholder: str
    options: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, key: _Optional[str] = ..., label: _Optional[str] = ..., type: _Optional[str] = ..., required: _Optional[bool] = ..., placeholder: _Optional[str] = ..., options: _Optional[_Iterable[str]] = ...) -> None: ...

class AgentDecl(_message.Message):
    __slots__ = ("key", "name", "description", "status", "model", "instructions", "tools")
    KEY_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    INSTRUCTIONS_FIELD_NUMBER: _ClassVar[int]
    TOOLS_FIELD_NUMBER: _ClassVar[int]
    key: str
    name: str
    description: str
    status: str
    model: ModelDecl
    instructions: _containers.RepeatedCompositeFieldContainer[InstructionDecl]
    tools: _containers.RepeatedCompositeFieldContainer[ToolDecl]
    def __init__(self, key: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., status: _Optional[str] = ..., model: _Optional[_Union[ModelDecl, _Mapping]] = ..., instructions: _Optional[_Iterable[_Union[InstructionDecl, _Mapping]]] = ..., tools: _Optional[_Iterable[_Union[ToolDecl, _Mapping]]] = ...) -> None: ...

class ModelDecl(_message.Message):
    __slots__ = ("provider", "name", "config")
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    provider: str
    name: str
    config: _struct_pb2.Struct
    def __init__(self, provider: _Optional[str] = ..., name: _Optional[str] = ..., config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class InstructionDecl(_message.Message):
    __slots__ = ("type", "format", "body", "position")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    type: str
    format: str
    body: str
    position: int
    def __init__(self, type: _Optional[str] = ..., format: _Optional[str] = ..., body: _Optional[str] = ..., position: _Optional[int] = ...) -> None: ...

class ToolDecl(_message.Message):
    __slots__ = ("key", "name", "description", "input_schema_json", "output_schema_json", "default_deadline_ms", "max_result_bytes", "sensitivity", "result_kind")
    KEY_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    INPUT_SCHEMA_JSON_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_SCHEMA_JSON_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_DEADLINE_MS_FIELD_NUMBER: _ClassVar[int]
    MAX_RESULT_BYTES_FIELD_NUMBER: _ClassVar[int]
    SENSITIVITY_FIELD_NUMBER: _ClassVar[int]
    RESULT_KIND_FIELD_NUMBER: _ClassVar[int]
    key: str
    name: str
    description: str
    input_schema_json: bytes
    output_schema_json: bytes
    default_deadline_ms: int
    max_result_bytes: int
    sensitivity: str
    result_kind: ResultKind
    def __init__(self, key: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., input_schema_json: _Optional[bytes] = ..., output_schema_json: _Optional[bytes] = ..., default_deadline_ms: _Optional[int] = ..., max_result_bytes: _Optional[int] = ..., sensitivity: _Optional[str] = ..., result_kind: _Optional[_Union[ResultKind, str]] = ...) -> None: ...

class ToolCallResponse(_message.Message):
    __slots__ = ("invocation_id", "result_json", "error", "duration_ms", "next_cursor", "total_rows")
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_JSON_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    TOTAL_ROWS_FIELD_NUMBER: _ClassVar[int]
    invocation_id: str
    result_json: bytes
    error: str
    duration_ms: int
    next_cursor: str
    total_rows: int
    def __init__(self, invocation_id: _Optional[str] = ..., result_json: _Optional[bytes] = ..., error: _Optional[str] = ..., duration_ms: _Optional[int] = ..., next_cursor: _Optional[str] = ..., total_rows: _Optional[int] = ...) -> None: ...

class Heartbeat(_message.Message):
    __slots__ = ("at",)
    AT_FIELD_NUMBER: _ClassVar[int]
    at: _timestamp_pb2.Timestamp
    def __init__(self, at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class HubMsg(_message.Message):
    __slots__ = ("hello_ack", "register_ack", "tool_call_request", "heartbeat_ack", "go_away", "credential_op_request")
    HELLO_ACK_FIELD_NUMBER: _ClassVar[int]
    REGISTER_ACK_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALL_REQUEST_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_ACK_FIELD_NUMBER: _ClassVar[int]
    GO_AWAY_FIELD_NUMBER: _ClassVar[int]
    CREDENTIAL_OP_REQUEST_FIELD_NUMBER: _ClassVar[int]
    hello_ack: HelloAck
    register_ack: RegisterAck
    tool_call_request: ToolCallRequest
    heartbeat_ack: HeartbeatAck
    go_away: GoAway
    credential_op_request: CredentialOpRequest
    def __init__(self, hello_ack: _Optional[_Union[HelloAck, _Mapping]] = ..., register_ack: _Optional[_Union[RegisterAck, _Mapping]] = ..., tool_call_request: _Optional[_Union[ToolCallRequest, _Mapping]] = ..., heartbeat_ack: _Optional[_Union[HeartbeatAck, _Mapping]] = ..., go_away: _Optional[_Union[GoAway, _Mapping]] = ..., credential_op_request: _Optional[_Union[CredentialOpRequest, _Mapping]] = ...) -> None: ...

class CredentialOpRequest(_message.Message):
    __slots__ = ("op_id", "op", "user_id", "user_email", "employee_no", "erp_identifier", "envelope_json", "deadline_ms")
    OP_ID_FIELD_NUMBER: _ClassVar[int]
    OP_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USER_EMAIL_FIELD_NUMBER: _ClassVar[int]
    EMPLOYEE_NO_FIELD_NUMBER: _ClassVar[int]
    ERP_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    ENVELOPE_JSON_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MS_FIELD_NUMBER: _ClassVar[int]
    op_id: str
    op: str
    user_id: str
    user_email: str
    employee_no: str
    erp_identifier: str
    envelope_json: bytes
    deadline_ms: int
    def __init__(self, op_id: _Optional[str] = ..., op: _Optional[str] = ..., user_id: _Optional[str] = ..., user_email: _Optional[str] = ..., employee_no: _Optional[str] = ..., erp_identifier: _Optional[str] = ..., envelope_json: _Optional[bytes] = ..., deadline_ms: _Optional[int] = ...) -> None: ...

class CredentialOpResponse(_message.Message):
    __slots__ = ("op_id", "ok", "error", "display")
    OP_ID_FIELD_NUMBER: _ClassVar[int]
    OK_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    op_id: str
    ok: bool
    error: str
    display: _struct_pb2.Struct
    def __init__(self, op_id: _Optional[str] = ..., ok: _Optional[bool] = ..., error: _Optional[str] = ..., display: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class HelloAck(_message.Message):
    __slots__ = ("connector_id", "organization_id", "namespace", "max_agents", "max_tools_per_agent", "max_concurrent_tool_calls")
    CONNECTOR_ID_FIELD_NUMBER: _ClassVar[int]
    ORGANIZATION_ID_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    MAX_AGENTS_FIELD_NUMBER: _ClassVar[int]
    MAX_TOOLS_PER_AGENT_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENT_TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    connector_id: str
    organization_id: str
    namespace: str
    max_agents: int
    max_tools_per_agent: int
    max_concurrent_tool_calls: int
    def __init__(self, connector_id: _Optional[str] = ..., organization_id: _Optional[str] = ..., namespace: _Optional[str] = ..., max_agents: _Optional[int] = ..., max_tools_per_agent: _Optional[int] = ..., max_concurrent_tool_calls: _Optional[int] = ...) -> None: ...

class RegisterAck(_message.Message):
    __slots__ = ("baseline_fingerprint", "status", "issues")
    BASELINE_FINGERPRINT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ISSUES_FIELD_NUMBER: _ClassVar[int]
    baseline_fingerprint: str
    status: str
    issues: _containers.RepeatedCompositeFieldContainer[DeclIssue]
    def __init__(self, baseline_fingerprint: _Optional[str] = ..., status: _Optional[str] = ..., issues: _Optional[_Iterable[_Union[DeclIssue, _Mapping]]] = ...) -> None: ...

class DeclIssue(_message.Message):
    __slots__ = ("path", "code", "message")
    PATH_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    path: str
    code: str
    message: str
    def __init__(self, path: _Optional[str] = ..., code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class ToolCallRequest(_message.Message):
    __slots__ = ("invocation_id", "agent_key", "tool_key", "args_json", "organization_id", "user_id", "conversation_id", "deadline_ms", "user_email", "employee_no", "erp_identifier", "erp_department_identifiers", "cursor", "page_size")
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    AGENT_KEY_FIELD_NUMBER: _ClassVar[int]
    TOOL_KEY_FIELD_NUMBER: _ClassVar[int]
    ARGS_JSON_FIELD_NUMBER: _ClassVar[int]
    ORGANIZATION_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MS_FIELD_NUMBER: _ClassVar[int]
    USER_EMAIL_FIELD_NUMBER: _ClassVar[int]
    EMPLOYEE_NO_FIELD_NUMBER: _ClassVar[int]
    ERP_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    ERP_DEPARTMENT_IDENTIFIERS_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    invocation_id: str
    agent_key: str
    tool_key: str
    args_json: bytes
    organization_id: str
    user_id: str
    conversation_id: str
    deadline_ms: int
    user_email: str
    employee_no: str
    erp_identifier: str
    erp_department_identifiers: _containers.RepeatedScalarFieldContainer[str]
    cursor: str
    page_size: int
    def __init__(self, invocation_id: _Optional[str] = ..., agent_key: _Optional[str] = ..., tool_key: _Optional[str] = ..., args_json: _Optional[bytes] = ..., organization_id: _Optional[str] = ..., user_id: _Optional[str] = ..., conversation_id: _Optional[str] = ..., deadline_ms: _Optional[int] = ..., user_email: _Optional[str] = ..., employee_no: _Optional[str] = ..., erp_identifier: _Optional[str] = ..., erp_department_identifiers: _Optional[_Iterable[str]] = ..., cursor: _Optional[str] = ..., page_size: _Optional[int] = ...) -> None: ...

class HeartbeatAck(_message.Message):
    __slots__ = ("at",)
    AT_FIELD_NUMBER: _ClassVar[int]
    at: _timestamp_pb2.Timestamp
    def __init__(self, at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GoAway(_message.Message):
    __slots__ = ("reason",)
    REASON_FIELD_NUMBER: _ClassVar[int]
    reason: str
    def __init__(self, reason: _Optional[str] = ...) -> None: ...
