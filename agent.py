
import os
import math
import requests

from dotenv import load_dotenv
from google import genai
from google.genai import types
# ============================================================
# ENGINEERING VALIDATION LAYER
# ============================================================

def validate_engineering_result(
    tool_name: str,
    arguments: dict,
    result: dict
) -> dict:
    """
    Independently validate engineering inputs and outputs.
    """

    import math

    errors = []
    warnings = []

    if result.get("status") != "SUCCESS":
        return {
            "validation_status": "REJECTED",
            "errors": ["Tool execution was not successful."],
            "warnings": warnings
        }

    if tool_name == "calculate_air_density":

        temperature = arguments.get("temperature_c")
        pressure = arguments.get("pressure_hpa")
        humidity = arguments.get("relative_humidity_pct")

        # 1. Validate inputs
        inputs = {
            "temperature": temperature,
            "pressure": pressure,
            "humidity": humidity
        }

        for name, value in inputs.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                errors.append(f"Invalid {name} input.")

        if errors:
            return {
                "validation_status": "REJECTED",
                "errors": errors,
                "warnings": warnings
            }

        if temperature <= -273.15:
            errors.append("Temperature is below absolute zero.")

        if pressure <= 0:
            errors.append("Absolute pressure must be positive.")

        if not 0 <= humidity <= 100:
            errors.append("Relative humidity must be between 0 and 100.")

        if errors:
            return {
                "validation_status": "REJECTED",
                "errors": errors,
                "warnings": warnings
            }

        # 2. Independently calculate expected moist-air density
        temperature_k = temperature + 273.15
        pressure_pa = pressure * 100

        R_d = 287.05
        R_v = 461.495

        saturation_pressure_hpa = (
            6.1121
            * math.exp(
                (18.678 - temperature / 234.5)
                * (temperature / (257.14 + temperature))
            )
        )

        vapour_pressure_pa = (
            humidity / 100
            * saturation_pressure_hpa
            * 100
        )

        dry_air_pressure_pa = pressure_pa - vapour_pressure_pa

        if dry_air_pressure_pa <= 0:
            errors.append("Invalid dry-air partial pressure.")

        if errors:
            return {
                "validation_status": "REJECTED",
                "errors": errors,
                "warnings": warnings
            }

        expected_moist_density = (
            dry_air_pressure_pa / (R_d * temperature_k)
            + vapour_pressure_pa / (R_v * temperature_k)
        )

        expected_dry_density = (
            pressure_pa / (R_d * temperature_k)
        )

        # 3. Compare tool output against independent calculation
        actual_moist_density = result.get(
            "moist_air_density_kg_m3"
        )

        actual_dry_density = result.get(
            "dry_air_density_kg_m3"
        )

        tolerance = 0.00015

        for name, value in [
            ("Moist-air density", actual_moist_density),
            ("Dry-air density", actual_dry_density)
        ]:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                errors.append(f"Invalid {name} output.")

        if not errors:

            moist_error = abs(
                actual_moist_density - expected_moist_density
            )

            dry_error = abs(
                actual_dry_density - expected_dry_density
            )

            if moist_error > tolerance:
                errors.append(
                    "Moist-air density failed independent verification."
                )

            if dry_error > tolerance:
                errors.append(
                    "Dry-air density failed independent verification."
                )

        # 4. Return verification evidence
        if errors:
            return {
                "validation_status": "REJECTED",
                "errors": errors,
                "warnings": warnings
            }

        return {
            "validation_status": "PASSED",
            "errors": [],
            "warnings": warnings,
            "independent_verification": {
                "expected_moist_density": round(
                    expected_moist_density, 6
                ),
                "reported_moist_density": actual_moist_density,
                "expected_dry_density": round(
                    expected_dry_density, 6
                ),
                "reported_dry_density": actual_dry_density,
                "absolute_tolerance": tolerance,
                "method": "Independent ideal gas mixture recalculation"
            }
        }

    return {
        "validation_status": "NOT_APPLICABLE",
        "errors": [],
        "warnings": ["No dedicated validation rule for this tool."]
    }
# ============================================================
# 1. CONFIGURATION
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from .env")

MODEL = "gemini-3.6-flash"
client = genai.Client(api_key=API_KEY)

SYSTEM_INSTRUCTION = """
You are PHALANX, an engineering environmental assessment agent.

You must:
1. Understand the user's civilian environmental assessment request.
2. Decide which registered environmental tools are required.
3. Invoke tools when their data is needed.
4. Interpret the returned data accurately.
5. Identify missing information and uncertainty.
6. Decide whether another permitted tool call is necessary.
7. Produce a structured, evidence-based response.

Rules:
- Never invent environmental measurements.
- Clearly distinguish weather model data from direct sensor observations.
- Terrain elevation is static geographic dataset information,
  not a live measurement.
- Identify unavailable data and API errors.
- Do not claim that a mission is safe or legally authorized.
- Do not generate flight paths, flight commands or aircraft control instructions.
- Do not assess or optimize evasion of weapons or weapon tracking.
- Do not fabricate engineering calculations.
"""

# ============================================================
# 2. TOOL 1: TERRAIN ELEVATION
# ============================================================

def get_elevation(latitude: float, longitude: float) -> dict:
    """
    Retrieve terrain elevation from the Open-Elevation dataset.
    """

    if not (-90 <= latitude <= 90):
        return {"status": "ERROR", "message": "Invalid latitude."}

    if not (-180 <= longitude <= 180):
        return {"status": "ERROR", "message": "Invalid longitude."}

    try:
        url = "https://api.open-elevation.com/api/v1/lookup"

        response = requests.get(
            url,
            params={"locations": f"{latitude},{longitude}"},
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

        elevation = data["results"][0]["elevation"]

        return {
            "status": "SUCCESS",
            "latitude": latitude,
            "longitude": longitude,
            "elevation_m": elevation,
            "source": "Open-Elevation",
            "data_type": "STATIC_TERRAIN_DATA"
        }

    except Exception as error:
        return {
            "status": "ERROR",
            "source": "Open-Elevation",
            "message": str(error)
        }


# ============================================================
# 3. TOOL 2: CURRENT WEATHER CONDITIONS
# ============================================================

def get_weather(latitude: float, longitude: float) -> dict:
    """
    Retrieve current model-based weather conditions
    from Open-Meteo.
    """

    if not (-90 <= latitude <= 90):
        return {"status": "ERROR", "message": "Invalid latitude."}

    if not (-180 <= longitude <= 180):
        return {"status": "ERROR", "message": "Invalid longitude."}

    try:
        url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "apparent_temperature,"
                "precipitation,"
                "rain,"
                "showers,"
                "weather_code,"
                "cloud_cover,"
                "pressure_msl,"
                "surface_pressure,"
                "wind_speed_10m,"
                "wind_direction_10m,"
                "wind_gusts_10m"
            ),
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "forecast_days": 1
        }

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()
        data = response.json()

        return {
            "status": "SUCCESS",
            "latitude": latitude,
            "longitude": longitude,
            "current": data.get("current"),
            "units": data.get("current_units"),
            "elevation_m": data.get("elevation"),
            "timezone": data.get("timezone"),
            "source": "Open-Meteo",
            "data_type": "CURRENT_MODEL_BASED_WEATHER"
        }

    except Exception as error:
        return {
            "status": "ERROR",
            "source": "Open-Meteo",
            "message": str(error)
        }

# ============================================================
# AIR DENSITY ENGINEERING CALCULATION
# ============================================================

def calculate_air_density(
    temperature_c: float,
    pressure_hpa: float,
    relative_humidity_pct: float
) -> dict:
    """
    Calculate moist-air density using the ideal gas mixture equation.

    Temperature: degrees Celsius
    Pressure: absolute pressure in hPa
    Relative humidity: percentage (0-100)
    """

    if temperature_c <= -273.15:
        return {
            "status": "ERROR",
            "message": "Temperature must be above absolute zero."
        }

    if pressure_hpa <= 0:
        return {
            "status": "ERROR",
            "message": "Absolute pressure must be positive."
        }

    if not 0 <= relative_humidity_pct <= 100:
        return {
            "status": "ERROR",
            "message": "Relative humidity must be between 0 and 100."
        }

    temperature_k = temperature_c + 273.15
    pressure_pa = pressure_hpa * 100

    # Specific gas constants
    R_d = 287.05
    R_v = 461.495

    # Saturation vapour pressure using Buck equation
    saturation_pressure_hpa = (
        6.1121
        * __import__("math").exp(
            (18.678 - temperature_c / 234.5)
            * (temperature_c / (257.14 + temperature_c))
        )
    )

    # Actual water vapour partial pressure
    vapour_pressure_pa = (
        relative_humidity_pct / 100
        * saturation_pressure_hpa
        * 100
    )

    # Dry-air partial pressure
    dry_air_pressure_pa = pressure_pa - vapour_pressure_pa

    if dry_air_pressure_pa <= 0:
        return {
            "status": "ERROR",
            "message": "Invalid dry-air partial pressure."
        }

    # Moist-air density
    dry_air_density = (
        dry_air_pressure_pa / (R_d * temperature_k)
    )

    vapour_density = (
        vapour_pressure_pa / (R_v * temperature_k)
    )

    moist_air_density = dry_air_density + vapour_density

    # Comparison against dry-air assumption
    dry_air_only_density = (
        pressure_pa / (R_d * temperature_k)
    )

    difference_pct = (
        (dry_air_only_density - moist_air_density)
        / dry_air_only_density
    ) * 100

    return {
        "status": "SUCCESS",
        "moist_air_density_kg_m3": round(moist_air_density, 4),
        "dry_air_density_kg_m3": round(dry_air_only_density, 4),
        "density_difference_percent": round(difference_pct, 3),
        "temperature_k": round(temperature_k, 2),
        "pressure_pa": round(pressure_pa, 2),
        "relative_humidity_percent": relative_humidity_pct,
        "vapour_pressure_pa": round(vapour_pressure_pa, 2),
        "dry_air_partial_pressure_pa": round(dry_air_pressure_pa, 2),
        "method": "Moist-air ideal gas mixture equation",
        "assumption": "Ideal gas mixture; saturation vapour pressure calculated using Buck equation"
    }
# ============================================================
# 4. GEMINI FUNCTION DECLARATIONS
# ============================================================

ELEVATION_TOOL = types.FunctionDeclaration(
    name="get_elevation",
    description=(
        "Retrieve terrain elevation in metres for a geographic "
        "coordinate using the Open-Elevation dataset."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "latitude": {
                "type": "NUMBER",
                "description": "Latitude in decimal degrees."
            },
            "longitude": {
                "type": "NUMBER",
                "description": "Longitude in decimal degrees."
            }
        },
        "required": ["latitude", "longitude"]
    }
)

WEATHER_TOOL = types.FunctionDeclaration(
    name="get_weather",
    description=(
        "Retrieve current model-based weather conditions, "
        "including temperature, humidity, precipitation, "
        "wind speed, wind direction and gusts."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "latitude": {
                "type": "NUMBER",
                "description": "Latitude in decimal degrees."
            },
            "longitude": {
                "type": "NUMBER",
                "description": "Longitude in decimal degrees."
            }
        },
        "required": ["latitude", "longitude"]
    }
)
AIR_DENSITY_TOOL = types.FunctionDeclaration(
    name="calculate_air_density",
    description=(
        "Calculate moist-air density using temperature, "
        "absolute atmospheric pressure and relative humidity. "
        "Use the actual values retrieved by get_weather whenever available."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "temperature_c": {
                "type": "NUMBER",
                "description": "Air temperature in degrees Celsius."
            },
            "pressure_hpa": {
                "type": "NUMBER",
                "description": "Absolute surface pressure in hPa."
            },
            "relative_humidity_pct": {
                "type": "NUMBER",
                "description": "Relative humidity as a percentage from 0 to 100."
            }
        },
        "required": [
            "temperature_c",
            "pressure_hpa",
            "relative_humidity_pct"
        ]
    }
)
REGISTERED_TOOLS = types.Tool(
    function_declarations=[
        ELEVATION_TOOL,
        WEATHER_TOOL,
        AIR_DENSITY_TOOL
    ]
)

# ============================================================
# 5. TOOL DISPATCHER
# ============================================================

def execute_tool(name: str, arguments: dict) -> dict:
    """
    Execute only explicitly registered Python tools.
    """

    allowed_tools = {
    "get_elevation": get_elevation,
    "get_weather": get_weather,
    "calculate_air_density": calculate_air_density
}

    if name not in allowed_tools:
        return {
            "status": "ERROR",
            "message": f"Unregistered tool: {name}"
        }

    try:
        return allowed_tools[name](**arguments)

    except Exception as error:
        return {
            "status": "ERROR",
            "message": str(error)
        }


# ============================================================
# 6. GEMINI AGENT LOOP
# ============================================================

def run_agent(user_request: str, max_steps: int = 5) -> dict:
    """
    Execute a bounded multi-step Gemini tool-calling loop.

    Gemini selects tools.
    Python executes registered tools.
    Python independently validates engineering results.
    Rejected results cannot be presented as verified.
    """

    if not user_request.strip():
        raise ValueError("User request cannot be empty.")

    if not 1 <= max_steps <= 10:
        raise ValueError("max_steps must be between 1 and 10.")

    history = [
        types.Content(
            role="user",
            parts=[types.Part(text=user_request)]
        )
    ]

    trace = []
    rejected_validations = []

    for step in range(max_steps):

        response = client.models.generate_content(
            model=MODEL,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[REGISTERED_TOOLS],
                temperature=0.2
            )
        )

        if not response.candidates:
            raise RuntimeError("Gemini returned no candidates.")

        candidate = response.candidates[0]
        history.append(candidate.content)

        function_calls = [
            part.function_call
            for part in (candidate.content.parts or [])
            if part.function_call is not None
        ]

        # Gemini has finished using tools.
        if not function_calls:

            # Never release a normal final report after a rejection.
            if rejected_validations:

                return {
                    "status": "VALIDATION_REJECTED",
                    "answer": (
                        "The agent could not issue a verified "
                        "engineering report because at least one "
                        "tool result failed independent validation. "
                        "Review the validation errors before using "
                        "the results."
                    ),
                    "rejected_validations": rejected_validations,
                    "steps": trace,
                    "tool_calls": len(trace)
                }

            return {
                "status": "COMPLETED",
                "answer": response.text or "",
                "steps": trace,
                "tool_calls": len(trace)
            }

        function_responses = []

        # Execute each tool selected by Gemini.
        for call in function_calls:

            arguments = dict(call.args or {})

            trace.append({
                "step": step + 1,
                "tool": call.name,
                "arguments": arguments
            })

            result = execute_tool(
                call.name,
                arguments
            )

            # Independently validate engineering results.
            validation = validate_engineering_result(
                call.name,
                arguments,
                result
            )

            result["validation"] = validation

            validation_status = validation.get(
                "validation_status",
                "NOT_CHECKED"
            )

            trace[-1]["result_status"] = result.get(
                "status",
                "UNKNOWN"
            )
            trace[-1]["validation_status"] = validation_status
            trace[-1]["validation"] = validation
            trace[-1]["tool_result"] = result

            # Record rejected results for the final-output safeguard.
            if validation_status == "REJECTED":

                rejection_record = {
                    "step": step + 1,
                    "tool": call.name,
                    "arguments": arguments,
                    "validation_errors": validation.get(
                        "errors",
                        []
                    )
                }

                rejected_validations.append(rejection_record)

                # Explicitly tell Gemini that this result is untrusted.
                result["agent_instruction"] = (
                    "VALIDATION REJECTED. Do not treat this result "
                    "as verified engineering data. Do not use it "
                    "as the basis for engineering conclusions. "
                    "Inspect the validation errors. You may attempt "
                    "a corrected calculation if appropriate, but "
                    "never claim that the rejected result passed."
                )

            function_responses.append(
                types.Part.from_function_response(
                    name=call.name,
                    response=result
                )
            )

        # Return tool results and validation evidence to Gemini.
        history.append(
            types.Content(
                role="user",
                parts=function_responses
            )
        )

    return {
        "status": "STEP_LIMIT_REACHED",
        "answer": (
            "The agent reached its maximum number of "
            "tool-calling rounds."
        ),
        "rejected_validations": rejected_validations,
        "steps": trace,
        "tool_calls": len(trace)
    }