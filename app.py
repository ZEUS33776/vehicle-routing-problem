from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, root_validator
from typing import List, Tuple
import time
from redis_queue import queue_task  # Import for Redis queue
import redis
import json
from config import API_KEY
from distance_matrix import create_distance_matrix

# Initialize FastAPI app
app = FastAPI()

# Connect to Redis
redis_conn = redis.StrictRedis(host="localhost", port=6379, db=0)

# Serve static files for Swagger UI
app.mount("/static", StaticFiles(directory="/home/ubuntu/my-flask-app/swagger-ui/dist"), name="static")

@app.get("/static/swagger.json")
async def swagger_json():
    return FileResponse("/home/ubuntu/my-flask-app/swagger-ui/dist/swagger.json")

@app.get("/swagger-ui/{path:path}")
async def serve_swagger_ui(path: str):
    full_path = f"/home/ubuntu/my-flask-app/swagger-ui/dist/{path}"
    return FileResponse(full_path)

@app.get("/swagger")
async def swagger_ui():
    return FileResponse("/home/ubuntu/my-flask-app/swagger-ui/dist/index.html")


# VRPRequest schema
class VRPRequest(BaseModel):
    coordinates: List[Tuple[float, float]]
    demands: List[int]
    vehicle_capacities: List[int]
    vehicle_max_distances: List[int]
    pickups_deliveries: List[Tuple[int, int]]
    num_vehicles: int = Field(..., gt=0, description="Number of vehicles (must be > 0)")
    depot: int
    starts: List[int]
    ends: List[int]

    @root_validator(pre=True)
    def validate_and_convert_pickups_deliveries(cls, values):
        pickups_deliveries = values.get("pickups_deliveries", [])
        if not all(isinstance(req, list) and len(req) == 2 for req in pickups_deliveries):
            raise ValueError("Each entry in pickups_deliveries must be a list with exactly two integers.")
        values["pickups_deliveries"] = [tuple(req) for req in pickups_deliveries]
        return values


@app.post("/solve")
async def solve_route(request: VRPRequest):
    try:
        # Generate the distance matrix
        dist_matrix = create_distance_matrix(request.coordinates)

        # Prepare data for Redis queue
        data = {
            "distance_matrix": dist_matrix,
            "demands": request.demands,
            "vehicle_capacities": request.vehicle_capacities,
            "vehicle_max_distances": request.vehicle_max_distances,
            "pickups_deliveries": request.pickups_deliveries,
            "num_vehicles": request.num_vehicles,
            "depot": request.depot,
            "starts": request.starts,
            "ends": request.ends,
        }

        # Submit the task to Redis queue
        task_id = queue_task(data)

        # Wait synchronously for the result
        max_wait_time = 10  # Maximum wait time in seconds
        wait_interval = 0.5  # Interval between polling
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            result = redis_conn.get(f"vrp_result:{task_id}")
            if result:
                # Return the result if found
                return JSONResponse(content=json.loads(result))
            time.sleep(wait_interval)  # Wait for the specified interval
            elapsed_time += wait_interval

        # If the result is not ready within the maximum wait time
        raise HTTPException(status_code=202, detail="Result is still being processed. Please try again later.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))