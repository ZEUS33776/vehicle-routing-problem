import pytest
from fastapi.testclient import TestClient
from app import app  # Import the FastAPI app from your main application code
from unittest.mock import patch

client = TestClient(app)

# Sample VRP request data
sample_vrp_request = {
    "coordinates": [
        [35.0527, -89.8502],  # depot (latitude, longitude)
        [35.0497, -89.9776],
        [35.1430, -90.0515],
        [35.1186, -89.9343],
        [35.1335, -89.9807],
        [35.1355, -90.0453],
        [35.1124, -89.9352],
        [35.1188, -90.0127],
        [35.1076, -89.9337],
        [35.1175, -89.9785],
        [35.1500, -89.9827],
        [35.1511, -90.0481],
        [35.1532, -90.0485],
        [35.0890, -89.8593],
        [35.1096, -89.8554],
        [35.1045, -89.8533]
    ],
    "demands": [0, 8, 9, 2, 4, 2, 4, 8, 8, 1, 2, 1, 2, 4, 4, 8],
    "vehicle_capacities":  [45, 55, 55, 55],
    "vehicle_max_distances":[90000, 80000, 80000, 70000],
    "pickups_deliveries": [(1, 6), (2, 7)],
    "num_vehicles": 4,
    "depot": 0,
    "starts": [0,0,0,0],
    "ends": [0,0,0,0]
}

# Test if /swagger is accessible
def test_swagger_ui():
    response = client.get("/swagger")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()  # Ensure the swagger UI is present

# Test the /solve endpoint with a valid VRP request
@patch("app.solve_cvrp")  # Mock the VRP solver function
def test_solve_route_valid_request(mock_solve_cvrp):
    # Mocking the solver function response
    mock_solve_cvrp.return_value = {"routes": "mocked_routes", "objective": 12345}

    # Make the request to the /solve endpoint
    response = client.post("/solve", json=sample_vrp_request)

    # Debugging: print the response content
    print(f"Response Content: {response.content}")

    # Assertions
    assert response.status_code == 200
    assert "routes" in response.json()  # Ensure that "routes" is in the response
    assert "objective" in response.json()  # Ensure that "objective" is also in the response

# Test the /solve endpoint with invalid data (missing required field)
def test_solve_route_invalid_request():
    invalid_request = sample_vrp_request.copy()
    del invalid_request["coordinates"]  # Remove coordinates to trigger validation error

    # Make the request to the /solve endpoint
    response = client.post("/solve", json=invalid_request)

    # Debugging: print the error response
    print(f"Error Response: {response.json()}")

    # Assertions
    assert response.status_code == 422  # Unprocessable Entity (invalid request)
    assert "detail" in response.json()  # Error message for missing field

# Test /static/swagger.json if the file is served correctly
def test_static_swagger_json():
    response = client.get("/static/swagger.json")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"  # Ensure correct content-type

# Test /static/swagger-ui/{path} if any swagger UI file is accessible
@pytest.mark.parametrize("path", ["index.html", "swagger-ui-bundle.js", "swagger-ui-standalone-preset.js"])
def test_static_swagger_ui_files(path):
    response = client.get(f"/swagger-ui/{path}")
    assert response.status_code == 200
    assert "Content-Type" in response.headers  # Ensure valid content-type is returned

# Test invalid URL format (wrong endpoint)
def test_invalid_endpoint():
    response = client.get("/invalid-endpoint")
    assert response.status_code == 404  # Not Found
