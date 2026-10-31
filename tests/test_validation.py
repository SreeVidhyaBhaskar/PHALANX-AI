
import pytest

from agent import (
    calculate_air_density,
    validate_engineering_result,
)


def test_valid_moist_air_calculation():
    arguments = {
        "temperature_c": 30.0,
        "pressure_hpa": 1010.7,
        "relative_humidity_pct": 70.0,
    }

    result = calculate_air_density(**arguments)

    assert result["status"] == "SUCCESS"
    assert result["moist_air_density_kg_m3"] > 0
    assert result["dry_air_density_kg_m3"] > 0
    assert result["dry_air_density_kg_m3"] > result["moist_air_density_kg_m3"]


def test_invalid_temperature():
    result = calculate_air_density(
        temperature_c=-274.0,
        pressure_hpa=1010.7,
        relative_humidity_pct=70.0,
    )

    assert result["status"] == "ERROR"


def test_invalid_pressure():
    result = calculate_air_density(
        temperature_c=30.0,
        pressure_hpa=0,
        relative_humidity_pct=70.0,
    )

    assert result["status"] == "ERROR"


def test_invalid_humidity():
    result = calculate_air_density(
        temperature_c=30.0,
        pressure_hpa=1010.7,
        relative_humidity_pct=120.0,
    )

    assert result["status"] == "ERROR"


def test_independent_validation_passes():
    arguments = {
        "temperature_c": 30.0,
        "pressure_hpa": 1010.7,
        "relative_humidity_pct": 70.0,
    }

    result = calculate_air_density(**arguments)

    validation = validate_engineering_result(
        "calculate_air_density",
        arguments,
        result,
    )

    assert validation["validation_status"] == "PASSED"


def test_corrupted_density_is_rejected():
    arguments = {
        "temperature_c": 30.0,
        "pressure_hpa": 1010.7,
        "relative_humidity_pct": 70.0,
    }

    result = calculate_air_density(**arguments)
    result["moist_air_density_kg_m3"] = 1.2500

    validation = validate_engineering_result(
        "calculate_air_density",
        arguments,
        result,
    )

    assert validation["validation_status"] == "REJECTED"


def test_invalid_humidity_is_rejected_by_validator():
    arguments = {
        "temperature_c": 30.0,
        "pressure_hpa": 1010.7,
        "relative_humidity_pct": 120.0,
    }

    result = calculate_air_density(
        temperature_c=30.0,
        pressure_hpa=1010.7,
        relative_humidity_pct=70.0,
    )

    validation = validate_engineering_result(
        "calculate_air_density",
        arguments,
        result,
    )

    assert validation["validation_status"] == "REJECTED"
