from __future__ import annotations

import io

from sci_etl_core.exceptions import LLMError, ParsingError, PipelineAborted

from sci_etl_cli.errors import CliFailure, ExitCode, describe_abort, missing_dependency_message, to_cli_failure


def test_unknown_package_suggests_reinstalling_the_cli():
    assert "pip install --force-reinstall sci-etl-cli" in missing_dependency_message("somepackage.module")


def test_nameless_import_error_is_reported_as_unknown():
    assert "'unknown'" in missing_dependency_message(None)


def test_failure_is_shown_on_the_given_stream_with_markup_escaped():
    stream = io.StringIO()
    CliFailure("bad [value]", ExitCode.CONFIGURATION).show(stream)
    assert stream.getvalue().strip() == "Error: bad [value]"


def test_abort_description_names_the_cause():
    try:
        try:
            raise LLMError("401 invalid api key")
        except LLMError as cause:
            raise PipelineAborted("Records kept failing", 2) from cause
    except PipelineAborted as aborted:
        description = describe_abort(aborted)
    assert description.endswith("cause: LLMError('401 invalid api key')")


def test_abort_without_a_cause_is_described_by_its_message():
    assert describe_abort(PipelineAborted("stopped", 0)) == "stopped (records processed before abort: 0)"


def test_other_library_errors_exit_one():
    failure = to_cli_failure(ParsingError("unreadable"))
    assert (failure.exit_code, failure.message) == (1, "unreadable")
