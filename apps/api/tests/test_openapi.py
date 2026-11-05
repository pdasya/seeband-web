import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from seeband_api.errors import ERROR_EXAMPLES
from seeband_api.export_openapi import main as export_main
from seeband_api.export_openapi import render_openapi
from seeband_api.main import create_app

CONTRACT = Path(__file__).parents[3] / "packages" / "api-client" / "openapi.json"


def test_checked_in_contract_matches_the_app() -> None:
    assert CONTRACT.read_text(encoding="utf-8") == render_openapi(), (
        "packages/api-client/openapi.json is out of date. Run `pnpm api:generate`."
    )


def test_export_writes_the_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "openapi.json"
    monkeypatch.setattr("sys.argv", ["export_openapi", str(output)])

    export_main()

    assert output.read_text(encoding="utf-8") == render_openapi()


def _operations(contract: dict[str, Any]) -> list[dict[str, Any]]:
    return [operation for path in contract["paths"].values() for operation in path.values()]


def test_every_operation_documents_the_error_format() -> None:
    contract = create_app().openapi()

    operations = _operations(contract)
    assert operations
    for operation in operations:
        schema = operation["responses"]["default"]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_contract_does_not_promise_fastapi_default_validation_error() -> None:
    assert "HTTPValidationError" not in json.dumps(create_app().openapi())


def _examples(contract: dict[str, Any], media: dict[str, Any]) -> list[Any]:
    """Examples a mock can serve for one response, whether named or on the schema."""
    named = [example["value"] for example in media.get("examples", {}).values()]
    name = media["schema"]["$ref"].rsplit("/", 1)[1]
    return named + contract["components"]["schemas"][name].get("examples", [])


def test_every_response_has_an_example_that_fits_its_schema() -> None:
    """The mock serves these examples, so a route without one would give made-up data."""
    contract = create_app().openapi()

    operations = _operations(contract)
    assert operations
    for operation in operations:
        for status, response in operation["responses"].items():
            media = response["content"]["application/json"]
            examples = _examples(contract, media)
            assert examples, f"{operation['operationId']} {status} has no example"
            validator = Draft202012Validator(
                {**media["schema"], "components": contract["components"]}
            )
            for example in examples:
                validator.validate(example)


@pytest.mark.parametrize("name", sorted(ERROR_EXAMPLES))
def test_every_operation_offers_the_named_error_examples(name: str) -> None:
    assert ERROR_EXAMPLES[name]["code"] == name
    for operation in _operations(create_app().openapi()):
        content = operation["responses"]["default"]["content"]["application/json"]
        assert content["examples"][name]["value"] == ERROR_EXAMPLES[name]


def test_operation_ids_are_function_names() -> None:
    contract = create_app().openapi()

    assert contract["paths"]["/api/health"]["get"]["operationId"] == "get_health"
